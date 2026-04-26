"""
RemoteLivenessModel — gateway-side HTTP proxy for the sidecar /liveness endpoint.

Companion to ``RemoteInsightFaceModel``. The api-gateway runs in Docker
(Linux ONNX Runtime, no CoreML EP) so any ONNX model that benefits from
the M5's Apple Neural Engine has to live in the native macOS ML sidecar.
This wrapper presents the same in-process ``LivenessModel.predict_batch``
shape so the realtime tracker can call it without caring about transport.

Boundary
--------
- One gateway-side instance per process; reused across calls. Holds an
  ``httpx.Client`` so the TCP connection stays warm for the per-frame
  call cadence (~5 fps in production).
- Stateless from the caller's perspective. The sidecar holds the ORT
  sessions; this class does JPEG encode + base64 + POST.

Failure policy
--------------
Treats the sidecar absence as the *signal* — not an error. ``healthcheck``
returns the parsed body or None; the caller decides whether to bind the
liveness path or skip it. Per-request failures raise ``RuntimeError``
that the realtime tracker's ``try/except`` already catches as "no
liveness for this frame", letting recognition proceed unimpeded so a
flaky network blip never blanks the live overlay.
"""

from __future__ import annotations

import base64
import logging

import cv2
import httpx
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class RemoteLivenessModel:
    """HTTP-proxy implementation of the in-process LivenessModel API.

    Mirrors ``LivenessModel.predict_batch`` exactly so the realtime
    tracker can swap implementations without seeing a difference.

    Args:
        base_url: Sidecar root URL, e.g. ``http://host.docker.internal:8001``.
            Same value the realtime SCRFD/ArcFace proxy uses.
        timeout: Per-request HTTP timeout (seconds). Reuses
            ``ML_SIDECAR_TIMEOUT_SECONDS`` because liveness shares the
            sidecar process with SCRFD + ArcFace and adds at most a few
            ms per face.
        jpeg_quality: 1-100. Reuses ``ML_SIDECAR_JPEG_QUALITY``.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | None = None,
        jpeg_quality: int | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout or settings.ML_SIDECAR_TIMEOUT_SECONDS
        self._jpeg_quality = jpeg_quality or settings.ML_SIDECAR_JPEG_QUALITY
        self._client = httpx.Client(timeout=self._timeout)
        # Sentinel for the realtime tracker's "model is bound" check —
        # mirrors the pattern in ``RemoteInsightFaceModel.app``.
        self.is_loaded = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def healthcheck(self) -> dict | None:
        """Probe the sidecar's ``/health`` and return only the liveness block.

        Used by the gateway lifespan to decide whether to bind the
        liveness model (only when ``loaded=True``). Doesn't raise —
        a missing/false body is the signal.
        """
        try:
            resp = self._client.get(f"{self._base_url}/health", timeout=3.0)
            if resp.status_code != 200:
                logger.warning(
                    "Liveness /health returned %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None
            body = resp.json()
            return body.get("liveness")
        except Exception as exc:
            logger.warning("Liveness /health unreachable: %s", exc)
            return None

    def close(self) -> None:
        """Close the underlying HTTP client. Idempotent."""
        try:
            self._client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Inference (mirrors LivenessModel.predict_batch)
    # ------------------------------------------------------------------

    def predict_batch(
        self,
        frame: np.ndarray,
        bboxes: list[tuple[int, int, int, int]],
    ) -> list[dict]:
        """Score N faces (one frame, N bboxes) via the sidecar.

        Args:
            frame: BGR ndarray. Single source frame for all bboxes.
            bboxes: list of (x1, y1, x2, y2) integer pixel coords. Empty
                list returns ``[]`` without doing any network work.

        Returns:
            list of dicts in the same order as ``bboxes``::

                [{"score": float, "label": "real"|"spoof",
                  "per_model_scores": {<name>: float, ...}}, ...]

            Caller decides what to do with the score (compare against
            ``LIVENESS_REAL_THRESHOLD`` etc.) — keeping the threshold
            decision out of the proxy means the sidecar response is
            entirely descriptive, not prescriptive.

        Raises:
            RuntimeError: JPEG encode failure, sidecar HTTP error, or
                response shape mismatch.
        """
        if not bboxes:
            return []

        jpeg = self._encode_jpeg(frame)
        if jpeg is None:
            raise RuntimeError("could not JPEG-encode frame for /liveness")

        payload = {
            "jpeg_b64": base64.b64encode(jpeg).decode("ascii"),
            "bboxes": [list(map(int, bbox)) for bbox in bboxes],
        }
        try:
            resp = self._client.post(
                f"{self._base_url}/liveness",
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            logger.warning("Sidecar /liveness (n=%d) failed: %s", len(bboxes), exc)
            raise RuntimeError(f"sidecar /liveness failed: {exc}") from exc

        preds = body.get("predictions") or []
        if len(preds) != len(bboxes):
            raise RuntimeError(
                f"sidecar /liveness returned {len(preds)} predictions; "
                f"requested {len(bboxes)}"
            )
        return preds

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _encode_jpeg(self, frame: np.ndarray) -> bytes | None:
        """Encode a BGR ndarray to JPEG bytes — same params as the embed proxy."""
        try:
            ok, buf = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(self._jpeg_quality)],
            )
            if not ok:
                return None
            return buf.tobytes()
        except Exception:
            logger.debug("JPEG encode failed for /liveness", exc_info=True)
            return None

    def __repr__(self) -> str:  # pragma: no cover — repr only
        return f"<RemoteLivenessModel url={self._base_url}>"
