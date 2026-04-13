"""
InsightFace Model

Unified face detection + 5-point alignment + ArcFace embedding using
InsightFace buffalo_l model pack. Single instance shared across registration
(selfie uploads) and CCTV recognition — same SCRFD detector, same ArcFace
embedder, so embeddings are numerically compatible between the two paths.

References:
  - ArcFace: Deng et al., CVPR 2019
  - SCRFD:   Guo et al., ICCV 2021
"""

import base64
import io
import platform
from dataclasses import dataclass

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
            logger.info(
                f"Loading InsightFace '{self._model_name}' (providers={providers}, det_size={self._det_size})..."
            )
            self.app = FaceAnalysis(name=self._model_name, providers=providers)
            self.app.prepare(ctx_id=0, det_size=self._det_size, det_thresh=settings.INSIGHTFACE_DET_THRESH)

            # NOTE: ORT session thread counts are controlled via OMP_NUM_THREADS
            # and MKL_NUM_THREADS environment variables set above, BEFORE
            # InsightFace creates its sessions.  The previous code here called
            # session.get_session_options() and set intra/inter_op_num_threads
            # on the returned object, but get_session_options() returns a COPY
            # — modifications have no effect on the live session.  Removed as
            # dead code.

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
