"""
LivenessModel — passive face anti-spoofing via MiniFASNet.

Why this exists
---------------
Phone screens, printed photos and tablet displays will trivially pass
identity recognition (ArcFace doesn't know it's looking at pixels-of-a-
face vs. a real face). MiniFASNet ("Silent Face Anti-Spoofing", MiniVision
Technologies, Apache-2.0) is the de facto open-source passive liveness
detector — a small CNN that takes a face crop and predicts
``{spoof_2D, real, spoof_3D}`` from texture / moiré / color cues alone,
no user action required.

Boundary
--------
- Loaded ONLY in the ML sidecar process. The api-gateway in Docker can't
  reach CoreML, so it routes calls here over HTTP via
  ``RemoteLivenessModel``. Same pattern as ``InsightFaceModel`` →
  ``RemoteInsightFaceModel`` for SCRFD + ArcFace.
- Stateless. One ONNX session pair per process; no DB, no cache, no
  per-track bookkeeping (the realtime tracker holds those in
  ``TrackIdentity``).
- Two-model fusion. Upstream's published deployment averages the
  softmax outputs of MiniFASNetV2 (scale 2.7) and MiniFASNetV1SE
  (scale 4.0). We do the same — single-model accuracy is noticeably
  worse on the printed-photo case. Both load on construction; the
  fused score is a single number per face that the tracker thresholds.

Failure policy
--------------
Constructor raises ``LivenessModelUnavailable`` if either ONNX file is
missing or the manifest is malformed. The sidecar catches this and
exposes ``liveness_loaded: False`` in ``/health`` so the gateway can
choose whether to gate recognition on liveness or skip it. Per-call
exceptions surface as 5xx HTTP responses; the gateway's per-frame
``try/except`` already catches those and treats them as "no liveness
information for this frame" — recognition continues unimpeded.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class LivenessModelUnavailable(RuntimeError):
    """Raised by ``LivenessModel`` when the on-disk pack can't be loaded.

    The sidecar treats this as "liveness not available for this process"
    and continues serving SCRFD + ArcFace. Operator action is to run
    ``python -m scripts.export_liveness_models`` to populate the pack.
    """


@dataclass(frozen=True)
class _LivenessSubmodel:
    """One of the two MiniFASNet variants in the fused predictor."""

    name: str
    onnx_path: Path
    scale: float
    input_size: int
    real_class_index: int
    session: object  # onnxruntime.InferenceSession (typed as object to avoid hard import here)
    input_name: str


@dataclass(frozen=True)
class LivenessPrediction:
    """Result of one face's liveness check.

    ``score`` is the fused softmax probability of the *real* class across
    both submodels — high = likely real, low = likely spoof. ``label`` is
    the human-readable threshold decision the realtime tracker uses to
    suppress recognition.
    """

    score: float
    label: str  # "real" | "spoof"
    per_model_scores: dict[str, float]


def _resolve_models_root() -> Path:
    """Honour ``INSIGHTFACE_HOME`` so the sidecar reads the same root
    the rest of the ML stack uses for buffalo_l_static."""
    root_env = os.environ.get("INSIGHTFACE_HOME")
    root = Path(root_env) if root_env else Path.home() / ".insightface"
    return root / "models"


def _get_providers() -> list[str]:
    """CoreML on macOS, CPU everywhere else.

    MiniFASNet is tiny (~2 MB per submodel, ~80x80 input) and the CoreML
    delegation buys ~3-5x over CPU on the M5. The same providers list
    pattern as ``InsightFaceModel._get_providers`` so the sidecar's
    /health introspection reports both face-recognition and liveness on
    the same execution provider.
    """
    if platform.system() == "Darwin":
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


class LivenessModel:
    """MiniFASNet-fused passive liveness detector.

    Initialise once at sidecar startup; reuse across requests. Call
    :meth:`predict_batch` with a list of (frame, bbox) pairs to score
    each face — bboxes share the source frame to amortise the JPEG
    decode + alignment overhead.
    """

    def __init__(self, pack_dir: Path | None = None):
        self._pack_dir = (pack_dir or _resolve_models_root() / "minifasnet").resolve()
        self._submodels: list[_LivenessSubmodel] = []
        self._manifest: dict | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Discover the pack on disk and create one ORT session per submodel.

        Raises ``LivenessModelUnavailable`` with a clear message when the
        pack is missing or malformed. The sidecar surfaces the message in
        ``/health`` so the operator sees it without having to tail logs.
        """
        manifest_path = self._pack_dir / "manifest.json"
        if not manifest_path.exists():
            raise LivenessModelUnavailable(
                f"Liveness manifest missing: {manifest_path}.\n"
                "Run `backend/venv/bin/python -m scripts.export_liveness_models` "
                "to generate the pack."
            )
        try:
            self._manifest = json.loads(manifest_path.read_text())
        except Exception as exc:
            raise LivenessModelUnavailable(
                f"Could not parse liveness manifest at {manifest_path}: {exc}"
            ) from exc

        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise LivenessModelUnavailable(
                "onnxruntime is required for liveness inference"
            ) from exc

        providers = _get_providers()
        # ORT spits warning messages on every session create when the
        # graph contains unsupported ops for the requested EP — silence
        # them at the SESSION level so the sidecar log stays readable.
        # Setting log_severity_level=3 (ERROR) on each session is the
        # supported way; the global ort.set_default_logger_severity is
        # set in the sidecar entrypoint already.
        sess_options = ort.SessionOptions()
        sess_options.log_severity_level = 3

        loaded: list[_LivenessSubmodel] = []
        for entry in self._manifest.get("models", []):
            onnx_filename = entry.get("onnx_filename")
            if not onnx_filename:
                logger.warning("Liveness manifest entry missing onnx_filename: %r", entry)
                continue
            onnx_path = self._pack_dir / onnx_filename
            if not onnx_path.exists():
                raise LivenessModelUnavailable(
                    f"Manifest references {onnx_filename} but {onnx_path} doesn't exist. "
                    "Re-run scripts.export_liveness_models with --force."
                )
            t0 = time.monotonic()
            session = ort.InferenceSession(
                str(onnx_path),
                sess_options=sess_options,
                providers=providers,
            )
            input_meta = session.get_inputs()[0]
            actual_providers = session.get_providers()
            logger.info(
                "Liveness submodel %s loaded in %.2fs — providers=%s, input=%s",
                onnx_filename,
                time.monotonic() - t0,
                actual_providers,
                input_meta.shape,
            )
            loaded.append(_LivenessSubmodel(
                name=str(entry.get("model_class") or onnx_filename),
                onnx_path=onnx_path,
                scale=float(entry.get("scale", 2.7)),
                input_size=int(entry.get("input_size", 80)),
                real_class_index=int(entry.get("real_class_index", 1)),
                session=session,
                input_name=input_meta.name,
            ))
        if not loaded:
            raise LivenessModelUnavailable(
                "No usable submodels found in liveness manifest"
            )
        self._submodels = loaded

    @property
    def is_loaded(self) -> bool:
        return bool(self._submodels)

    @property
    def info(self) -> dict:
        """Self-describing summary used by the sidecar's /health response."""
        return {
            "loaded": self.is_loaded,
            "pack_dir": str(self._pack_dir),
            "submodels": [
                {
                    "name": sm.name,
                    "onnx_filename": sm.onnx_path.name,
                    "scale": sm.scale,
                    "input_size": sm.input_size,
                    "providers": list(sm.session.get_providers()) if hasattr(sm.session, "get_providers") else [],
                }
                for sm in self._submodels
            ],
        }

    def warmup(self) -> None:
        """Run one synthetic forward through each submodel.

        Same rationale as ``InsightFaceModel.warmup``: ORT defers
        per-graph optimisation to the first inference. With CoreML on
        the M5 each MiniFASNet submodel pays a ~1-2 s JIT cost the first
        time we ask it to do work — pre-pay it during boot so the first
        real session pipeline doesn't see the lag.
        """
        if not self.is_loaded:
            return
        for sm in self._submodels:
            try:
                arr = np.zeros((1, 3, sm.input_size, sm.input_size), dtype=np.float32)
                sm.session.run(None, {sm.input_name: arr})
            except Exception:
                logger.debug("Liveness warmup failed for %s", sm.name, exc_info=True)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_batch(
        self,
        frame: np.ndarray,
        bboxes: list[tuple[int, int, int, int]],
    ) -> list[LivenessPrediction]:
        """Score every bbox in one frame with the fused predictor.

        Args:
            frame: BGR ndarray. Coordinate space of every bbox must match.
            bboxes: list of (x1, y1, x2, y2) integer pixel coordinates.
                Empty list returns ``[]`` without doing any work.

        Returns:
            List of ``LivenessPrediction`` in the same order as ``bboxes``.

        Raises:
            RuntimeError: Submodels not loaded. Call :meth:`load` first.
        """
        if not self.is_loaded:
            raise RuntimeError("LivenessModel not loaded — call load() first.")
        if not bboxes:
            return []

        src_h, src_w = frame.shape[:2]
        out: list[LivenessPrediction] = []

        # We could batch all bboxes through each submodel in one
        # session.run, but the static-shape ONNX has batch dim = 1, so
        # a single call per face is the right granularity for the CoreML
        # path. The submodels themselves are tiny (<1 ms inference),
        # so the per-call overhead is dominated by alignment + softmax.
        for bbox in bboxes:
            per_model: dict[str, float] = {}
            real_scores: list[float] = []
            for sm in self._submodels:
                crop = self._crop_for_submodel(frame, bbox, sm.scale, sm.input_size, src_w, src_h)
                if crop is None:
                    # Degenerate bbox — return spoof so the tracker
                    # suppresses the recognition for safety. Better to
                    # over-suppress than to commit a recognition based
                    # on a bbox we couldn't even crop.
                    real_scores.append(0.0)
                    per_model[sm.name] = 0.0
                    continue
                tensor = self._to_tensor(crop)
                try:
                    logits = sm.session.run(None, {sm.input_name: tensor})[0]
                except Exception:
                    logger.debug("Liveness session.run failed for %s", sm.name, exc_info=True)
                    real_scores.append(0.0)
                    per_model[sm.name] = 0.0
                    continue
                softmax = self._softmax(logits[0])
                real_p = float(softmax[sm.real_class_index])
                per_model[sm.name] = real_p
                real_scores.append(real_p)
            fused = float(sum(real_scores) / max(1, len(real_scores)))
            label = "real" if fused >= 0.5 else "spoof"
            out.append(LivenessPrediction(
                score=fused,
                label=label,
                per_model_scores=per_model,
            ))
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _crop_for_submodel(
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
        scale: float,
        input_size: int,
        src_w: int,
        src_h: int,
    ) -> np.ndarray | None:
        """Replicate upstream's ``anti_spoof_predict._get_new_box`` crop logic.

        MiniFASNet was trained with a deliberately *expanded* crop around
        the bbox so the model sees background context (lighting, halo,
        screen-bezel). Different submodels were trained at different
        scales (2.7 for V2, 4.0 for V1SE) so the fused predictor sees two
        different framings of the same face — averaging hides the failure
        modes of each.

        Skipping the scale would feed the model the wrong distribution
        and degrade real-face recall. Don't shortcut this even though
        the SCRFD bbox + ArcFace alignment crop are both already on hand.
        """
        x1, y1, x2, y2 = bbox
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        # Clip the requested scale so the expanded box can't escape
        # the frame even before centering — matches upstream behaviour.
        clipped_scale = min(scale, (src_h - 1) / box_h, (src_w - 1) / box_w)
        new_w = box_w * clipped_scale
        new_h = box_h * clipped_scale
        center_x = x1 + box_w / 2
        center_y = y1 + box_h / 2
        left = center_x - new_w / 2
        top = center_y - new_h / 2
        right = center_x + new_w / 2
        bottom = center_y + new_h / 2
        # Push back inside the frame if the centered box went off
        # an edge — keeps the requested area constant.
        if left < 0:
            right -= left
            left = 0
        if top < 0:
            bottom -= top
            top = 0
        if right > src_w - 1:
            left -= (right - src_w + 1)
            right = src_w - 1
        if bottom > src_h - 1:
            top -= (bottom - src_h + 1)
            bottom = src_h - 1
        l, t, r, b = int(left), int(top), int(right), int(bottom)
        if r <= l or b <= t:
            return None
        crop = frame[t:b, l:r]
        if crop.size == 0:
            return None
        try:
            return cv2.resize(crop, (input_size, input_size), interpolation=cv2.INTER_LINEAR)
        except Exception:
            return None

    @staticmethod
    def _to_tensor(crop_bgr: np.ndarray) -> np.ndarray:
        """HWC uint8 BGR → NCHW float32, no normalisation.

        Upstream's deploy code (``anti_spoof_predict.predict``) feeds the
        raw ``[0, 255]`` BGR float tensor directly to the model — there's
        no mean/std normalisation step. The model was trained with that
        same preprocessing, so we mirror it.
        """
        chw = np.transpose(crop_bgr, (2, 0, 1)).astype(np.float32, copy=False)
        return np.expand_dims(chw, 0)

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        """Numerically stable softmax over a 1-D logits vector."""
        shifted = logits - np.max(logits)
        exp = np.exp(shifted)
        return exp / np.sum(exp)
