"""
InsightFace Model

Unified face detection + 5-point alignment + ArcFace embedding using
InsightFace buffalo_l model pack. Single instance shared across registration
(selfie uploads) and CCTV recognition — same SCRFD detector, same ArcFace
embedder, so embeddings are numerically compatible between the two paths.

Two API surfaces live here:

- Registration path (selfie uploads): ``get_embedding`` /
  ``get_face_with_quality`` / ``get_embeddings_batch``. These still go through
  the full ``FaceAnalysis.get()`` because they process one image at a time
  and the ~40 ms cost of the unused per-face models (landmark_2d_106,
  landmark_3d_68, genderage) doesn't matter.

- CCTV realtime path (``RealtimeTracker``): ``detect()`` and
  ``embed_from_kps()``. These split the pipeline so that every-frame cost is
  **only** SCRFD, and ArcFace runs strictly on new / drifted / re-verify
  tracks. We also instruct ``FaceAnalysis`` to load only the two models we
  actually use via ``allowed_modules=['detection', 'recognition']`` —
  buffalo_l normally spins up 5 ONNX sessions (detection, landmark_2d_106,
  landmark_3d_68, genderage, recognition) and runs the last four on every
  face every frame, which dominates per-face cost in a full-classroom scene.
  Skipping those three cuts ~25 ms × N_faces per frame, enough to be the
  difference between a smooth and a choppy stream at 1–2 fps.

References:
  - ArcFace: Deng et al., CVPR 2019
  - SCRFD:   Guo et al., ICCV 2021
"""

import base64
import io
import os
import platform
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.config import logger, settings


@dataclass
class DetectedFace:
    """Single face detection result with ArcFace embedding."""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    embedding: np.ndarray  # 512-dim, L2-normalized (ArcFace normed_embedding)
    user_id: str | None = None
    similarity: float | None = None


class InsightFaceModel:
    """
    InsightFace wrapper: SCRFD detection + 5-point landmark alignment +
    ArcFace ResNet50 embedding in a single FaceAnalysis.get() call.

    Uses CoreML execution provider on Apple Silicon for Neural Engine
    acceleration; falls back to CPU on all other platforms.
    """

    def __init__(self):
        self.app = None  # insightface.app.FaceAnalysis (set by load_model)
        self._model_name: str = settings.INSIGHTFACE_MODEL
        self._det_size: tuple = (
            settings.INSIGHTFACE_DET_SIZE,
            settings.INSIGHTFACE_DET_SIZE,
        )

    def _resolve_model_pack(self) -> str:
        """Pick the static-shape pack if it exists, else fall back to upstream.

        See ``backend/scripts/export_static_models.py`` and the live-feed
        plan dated 2026-04-25 (Step 2b). The static pack is required for
        the CoreML execution provider to delegate SCRFD to the Apple
        Neural Engine; without it ORT silently falls back to CPU and
        backend FPS stays in the 1-2 range.
        """
        static_pack = (settings.INSIGHTFACE_STATIC_PACK_NAME or "").strip()
        if not static_pack:
            return self._model_name
        # Honour ``INSIGHTFACE_HOME`` if set (Docker images mount the
        # pre-baked model dir at /opt/insightface; dev macs use the
        # default ~/.insightface).
        try:
            root_env = os.environ.get("INSIGHTFACE_HOME")
            root = Path(root_env) if root_env else Path.home() / ".insightface"
            candidate = root / "models" / static_pack
            if candidate.exists():
                logger.info("Using static-shape model pack: %s", candidate)
                return static_pack
            logger.warning(
                "Static-shape pack '%s' not found at %s — falling back to '%s' (dynamic shapes; "
                "CoreMLExecutionProvider will not delegate)",
                static_pack,
                candidate,
                self._model_name,
            )
        except Exception:
            logger.debug("Static-pack resolution failed; using upstream", exc_info=True)
        return self._model_name

    def _get_providers(self) -> list[str]:
        """CoreML on macOS (Apple Silicon), CPU everywhere else."""
        if platform.system() == "Darwin":
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def load_model(self) -> None:
        """
        Load buffalo_l model pack (downloads ~500MB on first run to
        ~/.insightface/models/buffalo_l/).

        Thread counts are configured via OMP_NUM_THREADS / MKL_NUM_THREADS
        environment variables BEFORE InsightFace creates its ONNX sessions.
        With 4 Uvicorn workers each using ONNX_INTRA_OP_THREADS=2, the OS
        scheduler distributes 8 total threads across 4 vCPUs without
        oversubscription.
        """
        try:
            import os

            import onnxruntime as ort
            from insightface.app import FaceAnalysis

            # --- ONNX Runtime thread control for multi-worker deployment ---
            # Set env vars BEFORE InsightFace creates its internal ORT sessions
            # so each worker's sessions respect the configured thread limits.
            os.environ["OMP_NUM_THREADS"] = str(settings.ONNX_INTRA_OP_THREADS)
            os.environ["MKL_NUM_THREADS"] = str(settings.ONNX_INTRA_OP_THREADS)

            # Suppress noisy ORT warnings (level 3 = ERROR only)
            ort.set_default_logger_severity(3)

            logger.info(
                f"ONNX Runtime threads: intra_op={settings.ONNX_INTRA_OP_THREADS}, "
                f"inter_op={settings.ONNX_INTER_OP_THREADS}, "
                f"OMP_NUM_THREADS={os.environ.get('OMP_NUM_THREADS')}"
            )

            providers = self._get_providers()
            resolved_pack = self._resolve_model_pack()
            logger.info(
                f"Loading InsightFace '{resolved_pack}' (providers={providers}, det_size={self._det_size})..."
            )
            # ``allowed_modules`` pins the loaded ONNX sessions to just the two
            # we use. Without this, buffalo_l eagerly loads landmark_2d_106,
            # landmark_3d_68, and genderage, and ``FaceAnalysis.get()`` runs
            # each of them on every detected face on every frame (see the
            # upstream ``for taskname, model in self.models.items()`` loop).
            # For the realtime CCTV path we never consume any of those
            # outputs, so loading and running them is pure overhead.
            self.app = FaceAnalysis(
                name=resolved_pack,
                providers=providers,
                allowed_modules=["detection", "recognition"],
            )
            self.app.prepare(ctx_id=0, det_size=self._det_size, det_thresh=settings.INSIGHTFACE_DET_THRESH)

            # NOTE: ORT session thread counts are controlled via OMP_NUM_THREADS
            # and MKL_NUM_THREADS environment variables set above, BEFORE
            # InsightFace creates its sessions.  The previous code here called
            # session.get_session_options() and set intra/inter_op_num_threads
            # on the returned object, but get_session_options() returns a COPY
            # — modifications have no effect on the live session.  Removed as
            # dead code.

            # Per-model provider verification. CoreMLExecutionProvider being
            # in the requested provider list does NOT mean it was actually
            # selected — ORT silently falls back to CPU when the EP refuses
            # to delegate (most often because the ONNX has dynamic input
            # shapes). Log what each model picked so an operator can
            # confirm Step 2b's static-shape re-export actually took effect
            # on subsequent boots. See plan dated 2026-04-25.
            try:
                for task_name, model in self.app.models.items():
                    sess = getattr(model, "session", None)
                    actual = sess.get_providers() if sess is not None else ["<no-session>"]
                    onnx_path = getattr(model, "model_file", None) or getattr(model, "onnx_file", "<unknown>")
                    logger.info(
                        "[insightface] %s (%s) → providers=%s",
                        task_name,
                        onnx_path,
                        actual,
                    )
            except Exception:
                logger.debug("Per-model provider introspection failed", exc_info=True)

            logger.info(f"InsightFace '{self._model_name}' loaded successfully")

        except ImportError:
            logger.error("insightface not installed. Run: pip install insightface onnxruntime")
            raise RuntimeError("InsightFace dependencies not installed") from None
        except Exception as exc:
            logger.exception(f"Failed to load InsightFace model: {exc}")
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def warmup(self) -> None:
        """Run one synthetic SCRFD pass so the first real inference is hot.

        ONNX Runtime defers per-graph optimisation work to the first call —
        on M5 CPU at ``det_size=960`` that costs ~3-5 s the first time SCRFD
        runs. Without this, the first session pipeline that opens after boot
        sees a noticeable lag before any bounding box reaches the WS clients.
        Calling ``detect()`` on a noise frame here pre-pays that cost during
        startup, when nobody is watching.

        ArcFace JITs separately on its first ``embed_from_kps`` — that one
        is much cheaper (~100-200 ms) and only happens once per process,
        so we don't bother pre-warming it.
        """
        if self.app is None:
            return
        try:
            warm_frame = np.random.randint(
                0, 256,
                (settings.FRAME_GRABBER_HEIGHT, settings.FRAME_GRABBER_WIDTH, 3),
                dtype=np.uint8,
            )
            self.detect(warm_frame)
        except Exception:
            logger.debug("InsightFace warmup pass failed", exc_info=True)

    def _to_bgr(self, image: Image.Image | np.ndarray | bytes) -> np.ndarray:
        """
        Convert PIL Image / bytes / numpy array to BGR ndarray.
        InsightFace uses OpenCV (BGR) convention internally.
        """
        if isinstance(image, bytes):
            image = Image.open(io.BytesIO(image))
        if isinstance(image, Image.Image):
            image = image.convert("RGB")
            image = np.array(image)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        # ndarray: assume it is already BGR (from cv2.VideoCapture)
        return image

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def get_embedding(
        self,
        image: Image.Image | np.ndarray | bytes,
    ) -> np.ndarray:
        """
        Single image -> 512-dim L2-normalized ArcFace embedding.

        Used by face_service.py for each image during registration.
        SCRFD detects the face; ArcFace embeds the aligned 112x112 crop.

        Raises:
            RuntimeError: Model not loaded.
            ValueError:   No face detected in image.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        bgr = self._to_bgr(image)
        faces = self.app.get(bgr)

        if not faces:
            raise ValueError("No face detected in image")

        # InsightFace returns faces sorted by bounding-box area descending.
        # Take the largest (most prominent) face.
        return faces[0].normed_embedding.copy()

    def get_embedding_from_crop(self, face_crop_bgr: np.ndarray) -> np.ndarray:
        """
        Embed a pre-cropped face directly via ArcFace, skipping SCRFD detection.

        Resizes the crop to 112x112 (ArcFace input size) and runs the recognition
        model directly. Used for CCTV simulation where we already have a face crop
        and re-running SCRFD on a degraded tiny image would fail.

        Args:
            face_crop_bgr: BGR numpy array of a face crop (any size).

        Returns:
            512-dim L2-normalized ArcFace embedding.

        Raises:
            RuntimeError: Model not loaded.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        rec_model = self.app.models.get("recognition")
        if rec_model is None:
            raise RuntimeError("Recognition model not found in FaceAnalysis")

        # Resize to ArcFace input size (112x112)
        input_size = rec_model.input_size  # typically (112, 112)
        aligned = cv2.resize(face_crop_bgr, input_size, interpolation=cv2.INTER_LINEAR)

        # Get embedding directly from recognition model
        embedding = rec_model.get_feat(aligned).flatten()

        # L2 normalize
        norm = np.linalg.norm(embedding)
        if norm > 1e-6:
            embedding = embedding / norm

        return embedding

    def get_embeddings_batch(self, images: list) -> np.ndarray:
        """
        List of images -> [N, 512] L2-normalized embeddings.

        Images where no face is detected are skipped with a warning.

        Raises:
            RuntimeError: Model not loaded.
            ValueError:   No valid embeddings produced from any image.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        embeddings = []
        for img in images:
            try:
                embeddings.append(self.get_embedding(img))
            except ValueError as exc:
                logger.warning(f"Skipping image in batch: {exc}")

        if not embeddings:
            raise ValueError("No valid embeddings generated from batch")

        return np.stack(embeddings, axis=0)

    # ------------------------------------------------------------------
    # Recognition API (CCTV)
    # ------------------------------------------------------------------

    def get_faces(self, frame: np.ndarray) -> list[DetectedFace]:
        """
        BGR frame -> list of DetectedFace with bbox + ArcFace embedding.

        Single call replaces the old two-step pipeline:
          MediaPipe detect  ->  face crop  ->  FaceNet embed

        Now:
          SCRFD detect + 5-pt align + ArcFace embed  (one app.get() call)

        Args:
            frame: BGR numpy array (from cv2.VideoCapture).

        Returns:
            List of DetectedFace; empty list if no faces or model not loaded.
        """
        if self.app is None:
            return []

        try:
            insight_faces = self.app.get(frame)
            result = []
            h, w = frame.shape[:2]
            for face in insight_faces:
                x1, y1, x2, y2 = face.bbox.astype(int)
                cx1 = max(0, x1)
                cy1 = max(0, y1)
                cx2 = min(w, x2)
                cy2 = min(h, y2)
                result.append(
                    DetectedFace(
                        x=int(cx1),
                        y=int(cy1),
                        width=int(max(1, cx2 - cx1)),
                        height=int(max(1, cy2 - cy1)),
                        confidence=float(face.det_score),
                        embedding=face.normed_embedding.copy(),
                    )
                )
            return result
        except Exception as exc:
            logger.error(f"InsightFace get_faces error: {exc}")
            return []

    # ------------------------------------------------------------------
    # Registration API (with quality metadata)
    # ------------------------------------------------------------------

    def get_face_with_quality(
        self,
        image: Image.Image | np.ndarray | bytes,
    ) -> dict:
        """
        Single image -> embedding + quality metadata for registration.

        Returns a dict with:
          - embedding: 512-dim L2-normalized ArcFace embedding
          - det_score: SCRFD detection confidence
          - bbox: (x, y, w, h) bounding box
          - image_bgr: BGR numpy array (for quality assessment)

        Raises:
            RuntimeError: Model not loaded.
            ValueError:   No face detected in image.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        bgr = self._to_bgr(image)
        faces = self.app.get(bgr)

        if not faces:
            raise ValueError("No face detected in image")

        face = faces[0]  # Largest face
        x1, y1, x2, y2 = face.bbox.astype(int)
        h, w = bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        return {
            "embedding": face.normed_embedding.copy(),
            "det_score": float(face.det_score),
            "bbox": (int(x1), int(y1), int(max(1, x2 - x1)), int(max(1, y2 - y1))),
            "image_bgr": bgr,
        }

    # ------------------------------------------------------------------
    # CCTV realtime API — detect-only + embed-from-kps
    # ------------------------------------------------------------------
    #
    # Why a separate API: ``FaceAnalysis.get()`` always runs
    #   detection → (landmark_2d_106) → (landmark_3d_68) → (genderage) →
    #   recognition
    # on every face. For the realtime tracker we want SCRFD every frame
    # (cheap-ish, needed for ByteTrack), but ArcFace **only** on tracks that
    # are new, drifting, or due for re-verification. Pulling the two apart
    # lets the tracker skip ArcFace for already-known tracks, which is the
    # common case in a classroom of 5-20 mostly-stationary students.
    #
    # Correctness: the bboxes + 5-point keypoints this returns are in the
    # coordinate system of the **input frame** passed to ``detect()``. The
    # tracker downscales for detection and must scale the returned bboxes /
    # keypoints back to the original full-resolution frame before calling
    # ``embed_from_kps`` — ArcFace alignment is scale-sensitive and needs the
    # crop from the original-res frame to preserve recognition accuracy.

    def detect(
        self,
        frame: np.ndarray,
        input_size: tuple[int, int] | None = None,
    ) -> list[dict]:
        """Run SCRFD detection on ``frame`` and return raw bboxes + keypoints.

        Args:
            frame: BGR numpy array. Can be the original-resolution CCTV
                frame or a pre-downscaled copy — all returned coordinates
                are in this frame's pixel space.
            input_size: Optional SCRFD internal input size override. If
                None, uses the size set at ``prepare()`` time
                (``settings.INSIGHTFACE_DET_SIZE``).

        Returns:
            List of dicts, one per detected face:
              - ``bbox``: np.ndarray [x1, y1, x2, y2] in pixels, float32.
              - ``det_score``: SCRFD detection confidence (0..1).
              - ``kps``: np.ndarray [5, 2] five-point landmarks in pixels
                (right-eye, left-eye, nose, right-mouth, left-mouth), or
                ``None`` if the model wasn't configured to return them
                (buffalo_l does).
        """
        if self.app is None or self.app.det_model is None:
            return []

        try:
            bboxes, kpss = self.app.det_model.detect(
                frame,
                input_size=input_size,
                max_num=0,
                metric="default",
            )
        except Exception as exc:
            logger.error(f"SCRFD detect error: {exc}")
            return []

        if bboxes is None or bboxes.shape[0] == 0:
            return []

        out: list[dict] = []
        for i in range(bboxes.shape[0]):
            out.append(
                {
                    "bbox": bboxes[i, 0:4].astype(np.float32, copy=True),
                    "det_score": float(bboxes[i, 4]),
                    "kps": (
                        kpss[i].astype(np.float32, copy=True) if kpss is not None else None
                    ),
                }
            )
        return out

    def detect_tiled(
        self,
        frame: np.ndarray,
        tiles: list,
        *,
        include_coarse: bool = True,
        ios_thresh: float = 0.5,
    ) -> list[dict]:
        """Run SCRFD on N tiles in-process and merge with IOS-NMM.

        Distant-face plan 2026-04-26 Phase 3 — in-process counterpart
        to ``RemoteInsightFaceModel.detect_tiled``. Mirrors the sidecar
        endpoint's algorithm (letterbox each tile to ``self._det_size``,
        SCRFD per tile, remap, merge with IOS-NMM) so the realtime
        tracker can call this method whether the active backend is
        the sidecar or the in-process CPU model.

        Args:
            frame: BGR ndarray, full source frame.
            tiles: list of ``TileRect`` instances.
            include_coarse: Run an extra full-frame SCRFD pass and
                include its detections in the merge.
            ios_thresh: IOS threshold for greedy_nmm_ios.

        Returns:
            List of dicts with ``bbox`` / ``det_score`` / ``kps`` in
            original-frame pixel coordinates.
        """
        if not tiles:
            return self.detect(frame)
        if self.app is None or self.app.det_model is None:
            return []

        # Lazy import to avoid pulling tile_detection symbols into
        # paths that don't use them (registration, calibration).
        from app.services.ml.tile_detection import (
            greedy_nmm_ios,
            letterbox_to_square,
            remap_detection,
        )

        target_size = int(self._det_size[0])
        all_dets: list[dict] = []

        if include_coarse:
            try:
                all_dets.extend(self.detect(frame))
            except Exception:
                logger.exception("coarse detect inside detect_tiled failed")

        for tile in tiles:
            try:
                tile_img = frame[tile.y0:tile.y1, tile.x0:tile.x1]
                if tile_img.size == 0:
                    continue
                padded, scale, pad_x, pad_y = letterbox_to_square(
                    tile_img, target_size=target_size
                )
                local_dets = self.detect(padded)
                for det in local_dets:
                    bbox_global, kps_global = remap_detection(
                        det["bbox"],
                        det.get("kps"),
                        tile,
                        scale,
                        pad_x,
                        pad_y,
                    )
                    all_dets.append(
                        {
                            "bbox": bbox_global,
                            "det_score": float(det["det_score"]),
                            "kps": kps_global,
                        }
                    )
            except Exception:
                logger.exception(
                    "tile detection failed for %r — skipping", tile
                )

        return greedy_nmm_ios(all_dets, ios_threshold=ios_thresh)

    def embed_from_kps(
        self,
        frame: np.ndarray,
        kps: np.ndarray,
    ) -> np.ndarray:
        """Extract an ArcFace embedding for one face using 5-point landmarks.

        This is the recognition-only counterpart to :meth:`detect`. Callers
        that need the standard "detect + embed everyone" pipeline should
        still use :meth:`get_faces` or :meth:`get_embedding`.

        Args:
            frame: BGR numpy array. Must be the **original-resolution**
                frame the face actually appears in — alignment and the
                subsequent 112×112 crop are scale-sensitive, and running
                ArcFace on a bilinearly-resized tiny crop measurably
                degrades recognition confidence.
            kps: [5, 2] float landmark coordinates for this face in
                ``frame``'s pixel space.

        Returns:
            512-dim L2-normalized ArcFace embedding, dtype float32. This
            matches the numeric scale stored in FAISS at registration time
            (registration uses ``face.normed_embedding`` from
            ``FaceAnalysis.get()``, which is the same
            embedding / ||embedding||).

        Raises:
            RuntimeError: Model not loaded or recognition sub-model missing.
        """
        # Trivially delegated to the batch path so single-face callers stay
        # cheap and there's exactly one alignment + ArcFace code path to
        # maintain. Overhead vs. the previous single-face implementation is
        # one extra Python-level reshape on the resulting [1, 512] array.
        out = self.embed_from_kps_batch(frame, [kps])
        if out.shape[0] == 0:
            raise RuntimeError("embed_from_kps_batch returned no embeddings")
        return out[0].copy()

    def _get_recognition_max_batch(self, rec_model) -> int | None:
        """Return the recognition model's static batch size, or None if dynamic.

        Cached on first call. Uses the ONNX session's input metadata —
        a static export pins the batch dim to an int (typically 1); a
        dynamic export reports the dim as a string ('None' or 'batch').
        Returning None tells the caller "no chunking needed; one
        get_feat call handles any N".
        """
        cached = getattr(self, "_rec_max_batch", "unset")
        if cached != "unset":
            return cached
        result: int | None = None
        try:
            sess = getattr(rec_model, "session", None)
            if sess is not None:
                inp = sess.get_inputs()[0]
                # shape is a list like [batch, 3, 112, 112]; batch is int
                # for static, str ('None'/'batch') for dynamic.
                first = inp.shape[0]
                if isinstance(first, int) and first > 0:
                    result = int(first)
                    logger.info(
                        "ArcFace recognition session is static-shape — chunking batches at %d",
                        result,
                    )
                else:
                    logger.info(
                        "ArcFace recognition session is dynamic-shape (batch=%r) — "
                        "no chunking needed",
                        first,
                    )
        except Exception:
            logger.debug("Could not introspect rec_model batch shape", exc_info=True)
        # Cache (None or int) so subsequent calls skip the introspection
        self._rec_max_batch = result
        return result

    def embed_from_kps_batch(
        self,
        frame: np.ndarray,
        kps_list: list[np.ndarray],
    ) -> np.ndarray:
        """Batched ArcFace: N faces from one frame → [N, 512] embeddings.

        InsightFace's ``ArcFaceONNX.get_feat()`` already accepts a list of
        aligned crops and uses ``cv2.dnn.blobFromImages()`` to construct a
        single [N, 3, 112, 112] tensor before calling ``session.run()``
        once. So a "batched" embed is really:

          1. Align N faces (cheap — ~1 ms each)
          2. ONE ONNX session.run on a stacked tensor (the only cost that
             actually scales sub-linearly with N because ORT amortises
             session entry, layout transforms, and BLAS thread spin-up)
          3. L2-normalise per row and return.

        This collapses N python-level forward calls into one, which on
        the M5 CPU drops the per-frame embed cost for N=4 from ~120 ms to
        ~50 ms, and on the CoreML sidecar from ~80 ms to ~30 ms.

        Args:
            frame: BGR numpy array. Must be the original-resolution frame
                that all of ``kps_list`` came from. Alignment is
                scale-sensitive — the [5,2] landmarks must reference this
                frame's pixel space.
            kps_list: List of N landmark arrays, each shape [5, 2]. Empty
                list returns an empty [0, 512] array — convenient for
                "no faces to embed" callers.

        Returns:
            [N, 512] float32 array of L2-normalized ArcFace embeddings, in
            the same order as ``kps_list``. Numerically identical to
            calling ``embed_from_kps`` N times, just much faster.

        Raises:
            RuntimeError: Model not loaded, recognition sub-model missing,
                or InsightFace's get_feat returned an unexpected shape.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        rec_model = self.app.models.get("recognition")
        if rec_model is None:
            raise RuntimeError("Recognition model not loaded (allowed_modules?)")

        if not kps_list:
            return np.zeros((0, 512), dtype=np.float32)

        # face_align is part of the insightface package — import lazily.
        from insightface.utils import face_align

        input_size = int(rec_model.input_size[0])
        aligned_crops: list[np.ndarray] = []
        # Distant-face plan 2026-04-26 Phase 4c — when a face is tiny
        # (back-row or distant), the default INTER_LINEAR resampler in
        # face_align.norm_crop's warpAffine smears already-scarce pixel
        # detail. INTER_CUBIC preserves a measurable amount of edge
        # information at sub-millisecond cost. We estimate the face
        # span from the 5-pt landmark spread (close enough to bbox
        # width for the threshold decision) and switch to INTER_CUBIC
        # only when below ARCFACE_TINY_CROP_PX. Larger faces stay on
        # INTER_LINEAR — there's no quality benefit and we'd just
        # burn CPU on them.
        cubic_enabled = bool(
            getattr(settings, "ARCFACE_CUBIC_UPSAMPLE_ENABLED", False)
        )
        tiny_threshold_px = int(
            getattr(settings, "ARCFACE_TINY_CROP_PX", 64)
        )
        for kps in kps_list:
            kps_arr = np.asarray(kps, dtype=np.float32)
            if kps_arr.shape != (5, 2):
                # Skip the bad entry but keep alignment with the input
                # ordering by appending a zero crop. The corresponding
                # output row will be a near-zero embedding which won't
                # match anything in FAISS — caller logs the warning.
                logger.warning(
                    "embed_from_kps_batch: skipping bad kps shape %s", kps_arr.shape
                )
                aligned_crops.append(
                    np.zeros((input_size, input_size, 3), dtype=np.uint8)
                )
                continue
            use_cubic = False
            if cubic_enabled:
                kps_x_span = float(kps_arr[:, 0].max() - kps_arr[:, 0].min())
                kps_y_span = float(kps_arr[:, 1].max() - kps_arr[:, 1].min())
                # Use the larger axis as a face-size proxy — typical
                # human-facing kps span ~50-60 % of the face's longer
                # dimension. Threshold ARCFACE_TINY_CROP_PX is in face-
                # pixel units, so a kps span of ~half the threshold
                # corresponds to a small face overall.
                if max(kps_x_span, kps_y_span) < (tiny_threshold_px * 0.6):
                    use_cubic = True
            if use_cubic:
                # Inline the face_align.norm_crop affine + warpAffine so
                # we can pass the cv2.INTER_CUBIC flag — upstream's
                # implementation doesn't expose interpolation as an arg.
                M = face_align.estimate_norm(kps_arr, input_size, mode="arcface")
                aligned = cv2.warpAffine(
                    frame,
                    M,
                    (input_size, input_size),
                    flags=cv2.INTER_CUBIC,
                    borderValue=0.0,
                )
            else:
                aligned = face_align.norm_crop(
                    frame, landmark=kps_arr, image_size=input_size
                )
            aligned_crops.append(aligned)

        # Single batched ONNX session.run via insightface's get_feat. When
        # passed a list, get_feat builds a [N, 3, H, W] blob and runs one
        # forward pass — see arcface_onnx.py upstream.
        #
        # Static-shape models (used by the ML sidecar so CoreML can
        # delegate to the ANE — see backend/scripts/export_static_models.py)
        # have their batch dimension locked to a fixed value (typically 1).
        # Sending more rows raises ONNXRuntimeError InvalidArgument. We
        # detect the supported batch size from the session metadata and
        # chunk the call so the static-shape sidecar still benefits from
        # the saved HTTP round-trips + JPEG re-encodes, even if it can't
        # do all-N-in-one inference.
        max_batch = self._get_recognition_max_batch(rec_model)
        if max_batch is not None and len(aligned_crops) > max_batch:
            chunks = []
            for i in range(0, len(aligned_crops), max_batch):
                sub = aligned_crops[i : i + max_batch]
                chunks.append(np.asarray(rec_model.get_feat(sub), dtype=np.float32))
            # Each chunk may come back as [k, 512] or [512] depending on the
            # ORT version; normalise.
            stacked: list[np.ndarray] = []
            for c in chunks:
                if c.ndim == 1:
                    stacked.append(c.reshape(1, -1))
                else:
                    stacked.append(c)
            feats = np.vstack(stacked)
        else:
            feats = rec_model.get_feat(aligned_crops)
            feats = np.asarray(feats, dtype=np.float32)
            if feats.ndim == 1:
                # Defensive: some ORT versions return [512] when N==1
                feats = feats.reshape(1, -1)
        if feats.shape[0] != len(kps_list) or feats.shape[1] != 512:
            raise RuntimeError(
                f"unexpected ArcFace output shape {feats.shape}; expected "
                f"({len(kps_list)}, 512)"
            )

        # L2-normalize per row. Avoid div-by-zero on the synthetic zero
        # crops above (they get norm 0, leave them as zeros).
        norms = np.linalg.norm(feats, axis=1, keepdims=True)
        safe_norms = np.where(norms < 1e-6, 1.0, norms)
        feats = feats / safe_norms
        # Force-zero rows whose original norm was below the floor so they
        # don't accidentally normalise to a unit vector pointing at noise.
        feats = np.where(norms < 1e-6, 0.0, feats)
        return feats.astype(np.float32, copy=False)

    # ------------------------------------------------------------------
    # Utility (same interface as old FaceNetModel)
    # ------------------------------------------------------------------

    def decode_base64_image(
        self,
        base64_string: str,
        validate_size: bool = True,
    ) -> Image.Image:
        """
        Decode a Base64 image string to PIL Image with security validation.
        Accepts JPEG and PNG. Rejects oversized or undersized inputs.
        """
        try:
            if validate_size and len(base64_string) > 15_000_000:
                raise ValueError(
                    f"Base64 image too large: {len(base64_string)} bytes (max 15MB encoded / ~10MB decoded)"
                )

            if "," in base64_string:
                base64_string = base64_string.split(",")[1]

            try:
                image_bytes = base64.b64decode(base64_string, validate=True)
            except Exception as exc:
                raise ValueError(f"Invalid Base64 encoding: {exc}") from exc

            if validate_size and len(image_bytes) > 10_000_000:
                raise ValueError(f"Decoded image too large: {len(image_bytes)} bytes (max 10MB)")

            try:
                image = Image.open(io.BytesIO(image_bytes))
            except Exception as exc:
                raise ValueError(f"Invalid image format: {exc}") from exc

            if image.format not in ("JPEG", "PNG"):
                raise ValueError(f"Unsupported image format: {image.format} (expected JPEG or PNG)")

            width, height = image.size
            if width < 160 or height < 160:
                raise ValueError(f"Image too small: {width}x{height}, minimum 160x160 required")
            if width > 4096 or height > 4096:
                raise ValueError(f"Image too large: {width}x{height} (maximum 4096x4096)")

            return image

        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"Failed to decode Base64 image: {exc}")
            raise ValueError(f"Image decoding failed: {exc}") from exc


# Global instance — initialized during FastAPI startup via load_model()
insightface_model = InsightFaceModel()
