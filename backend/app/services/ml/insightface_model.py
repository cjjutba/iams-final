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
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        rec_model = self.app.models.get("recognition")
        if rec_model is None:
            raise RuntimeError("Recognition model not loaded (allowed_modules?)")

        # ``face_align`` is part of the insightface package. Import lazily so
        # a missing dep doesn't break module import at app startup — the
        # recognition path is optional during registration-only deployments.
        from insightface.utils import face_align

        aligned = face_align.norm_crop(
            frame, landmark=kps, image_size=rec_model.input_size[0]
        )
        raw = rec_model.get_feat(aligned).flatten()
        norm = float(np.linalg.norm(raw))
        if norm > 1e-6:
            raw = raw / norm
        return raw.astype(np.float32, copy=False)

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
