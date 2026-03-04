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
from typing import List, Optional, Union

import cv2
import numpy as np
from PIL import Image

from app.config import settings, logger


@dataclass
class DetectedFace:
    """Single face detection result with ArcFace embedding."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    embedding: np.ndarray       # 512-dim, L2-normalized (ArcFace normed_embedding)
    user_id: Optional[str] = None
    similarity: Optional[float] = None


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

    def _get_providers(self) -> List[str]:
        """CoreML on macOS (Apple Silicon), CPU everywhere else."""
        if platform.system() == "Darwin":
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def load_model(self) -> None:
        """
        Load buffalo_l model pack (downloads ~500MB on first run to
        ~/.insightface/models/buffalo_l/).
        """
        try:
            from insightface.app import FaceAnalysis

            providers = self._get_providers()
            logger.info(
                f"Loading InsightFace '{self._model_name}' "
                f"(providers={providers}, det_size={self._det_size})..."
            )
            self.app = FaceAnalysis(name=self._model_name, providers=providers)
            self.app.prepare(ctx_id=0, det_size=self._det_size)
            logger.info(f"InsightFace '{self._model_name}' loaded successfully")

        except ImportError:
            logger.error(
                "insightface not installed. Run: pip install insightface onnxruntime"
            )
            raise RuntimeError("InsightFace dependencies not installed")
        except Exception as exc:
            logger.exception(f"Failed to load InsightFace model: {exc}")
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_bgr(self, image: Union[Image.Image, np.ndarray, bytes]) -> np.ndarray:
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
        image: Union[Image.Image, np.ndarray, bytes],
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

    def get_embeddings_batch(self, images: List) -> np.ndarray:
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

    def get_faces(self, frame: np.ndarray) -> List[DetectedFace]:
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
                    f"Base64 image too large: {len(base64_string)} bytes "
                    "(max 15MB encoded / ~10MB decoded)"
                )

            if "," in base64_string:
                base64_string = base64_string.split(",")[1]

            try:
                image_bytes = base64.b64decode(base64_string, validate=True)
            except Exception as exc:
                raise ValueError(f"Invalid Base64 encoding: {exc}")

            if validate_size and len(image_bytes) > 10_000_000:
                raise ValueError(
                    f"Decoded image too large: {len(image_bytes)} bytes (max 10MB)"
                )

            try:
                image = Image.open(io.BytesIO(image_bytes))
            except Exception as exc:
                raise ValueError(f"Invalid image format: {exc}")

            if image.format not in ("JPEG", "PNG"):
                raise ValueError(
                    f"Unsupported image format: {image.format} (expected JPEG or PNG)"
                )

            width, height = image.size
            if width < 160 or height < 160:
                raise ValueError(
                    f"Image too small: {width}x{height}, minimum 160x160 required"
                )
            if width > 4096 or height > 4096:
                raise ValueError(
                    f"Image too large: {width}x{height} (maximum 4096x4096)"
                )

            return image

        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"Failed to decode Base64 image: {exc}")
            raise ValueError(f"Image decoding failed: {exc}")


# Global instance — initialized during FastAPI startup via load_model()
insightface_model = InsightFaceModel()
