"""
Face Recognition Module

Wrapper for FaceNet model to generate face embeddings.
Uses InceptionResnetV1 pretrained on VGGFace2 dataset.
"""

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import io
import base64
from typing import Optional, Union

from facenet_pytorch import MTCNN

from app.config import settings, logger


class FaceNetModel:
    """
    FaceNet model wrapper for generating face embeddings

    Uses InceptionResnetV1 architecture pretrained on VGGFace2.
    Generates 512-dimensional embeddings for face recognition.
    """

    def __init__(self):
        """Initialize FaceNet model with GPU/CPU fallback"""
        self.device = self._get_device()
        self.model: Optional[nn.Module] = None
        self.image_size = settings.FACE_IMAGE_SIZE  # 160x160

    def _get_device(self) -> torch.device:
        """
        Determine device (GPU or CPU) for model inference

        Returns:
            torch.device: Selected device
        """
        if torch.cuda.is_available() and settings.USE_GPU:
            logger.info("Using GPU (CUDA) for face recognition")
            return torch.device('cuda')
        else:
            if settings.USE_GPU:
                logger.warning("GPU requested but not available, using CPU")
            else:
                logger.info("Using CPU for face recognition")
            return torch.device('cpu')

    def _init_mtcnn(self):
        """Initialize MTCNN for face alignment (lazy)."""
        if not hasattr(self, '_mtcnn') or self._mtcnn is None:
            self._mtcnn = MTCNN(
                image_size=self.image_size,
                margin=0,
                min_face_size=20,
                select_largest=True,
                post_process=False,
                device=self.device if self.device else torch.device('cpu')
            )
            logger.info("MTCNN initialized for face alignment")

    def align_face(self, image: Image.Image) -> Optional[Image.Image]:
        """Align face using MTCNN landmarks. Returns aligned PIL Image or None."""
        try:
            self._init_mtcnn()
            aligned = self._mtcnn(image)
            if aligned is None:
                logger.debug("MTCNN found no face landmarks — skipping alignment")
                return None
            # MTCNN returns tensor in [0, 255] when post_process=False
            aligned_np = aligned.permute(1, 2, 0).cpu().numpy().astype(np.uint8)
            return Image.fromarray(aligned_np)
        except Exception as e:
            logger.warning(f"MTCNN alignment failed: {e} — falling back to raw crop")
            return None

    def load_model(self):
        """
        Load FaceNet model

        Loads InceptionResnetV1 pretrained on VGGFace2 dataset.
        Model is set to evaluation mode and moved to selected device.
        """
        try:
            from facenet_pytorch import InceptionResnetV1

            logger.info("Loading FaceNet model (InceptionResnetV1)...")
            self.model = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)
            logger.info(f"FaceNet model loaded successfully on {self.device}")

        except ImportError:
            logger.error("facenet-pytorch not installed. Run: pip install facenet-pytorch")
            raise RuntimeError("Face recognition dependencies not installed")
        except Exception as e:
            logger.exception(f"Failed to load FaceNet model: {e}")
            raise

    def preprocess_image(self, image: Union[Image.Image, np.ndarray]) -> torch.Tensor:
        """
        Preprocess image for FaceNet input

        - Resize to 160x160
        - Convert to RGB
        - Normalize to [-1, 1]
        - Convert to tensor

        Args:
            image: PIL Image or numpy array

        Returns:
            Preprocessed tensor [1, 3, 160, 160]
        """
        # Convert numpy array to PIL if needed
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        # Ensure RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize to model input size
        image = image.resize((self.image_size, self.image_size), Image.BILINEAR)

        # Convert to numpy array and normalize to [-1, 1]
        img_array = np.array(image, dtype=np.float32)
        img_array = (img_array - 127.5) / 128.0  # Normalize to [-1, 1]

        # Convert to tensor: [H, W, C] -> [C, H, W]
        img_tensor = torch.from_numpy(img_array).permute(2, 0, 1)

        # Add batch dimension: [C, H, W] -> [1, C, H, W]
        img_tensor = img_tensor.unsqueeze(0)

        return img_tensor.to(self.device)

    def generate_embedding(self, image: Union[Image.Image, np.ndarray, bytes]) -> np.ndarray:
        """
        Generate 512-dimensional face embedding

        Args:
            image: PIL Image, numpy array, or bytes (JPEG/PNG)

        Returns:
            512-dimensional embedding as numpy array

        Raises:
            RuntimeError: If model not loaded
            ValueError: If image processing fails
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        try:
            # Handle bytes input (from API)
            if isinstance(image, bytes):
                image = Image.open(io.BytesIO(image))

            # Attempt MTCNN face alignment if enabled
            if settings.USE_FACE_ALIGNMENT:
                aligned = self.align_face(image)
                if aligned is not None:
                    image = aligned

            # Preprocess image
            img_tensor = self.preprocess_image(image)

            # Generate embedding
            with torch.no_grad():
                embedding = self.model(img_tensor)

            # Convert to numpy and normalize (L2 normalization for cosine similarity)
            embedding_np = embedding.cpu().numpy()[0]
            embedding_np = embedding_np / np.linalg.norm(embedding_np)

            return embedding_np

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise ValueError(f"Image processing failed: {e}")

    def generate_embeddings_batch(self, images: list) -> np.ndarray:
        """
        Generate embeddings for multiple images in a single forward pass.

        Uses torch.cat to batch all preprocessed tensors and runs them
        through the model in one GPU/CPU call — much faster than sequential
        generate_embedding() calls for large batches (e.g. 40+ faces).

        Args:
            images: List of PIL Images, numpy arrays, or bytes

        Returns:
            Array of embeddings [N, 512]

        Raises:
            RuntimeError: If model not loaded
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        tensors = []
        for img in images:
            try:
                if isinstance(img, bytes):
                    img = Image.open(io.BytesIO(img))
                tensors.append(self.preprocess_image(img))  # [1, 3, 160, 160]
            except Exception as e:
                logger.warning(f"Failed to preprocess image in batch: {e}")
                continue

        if not tensors:
            raise ValueError("No valid embeddings generated from batch")

        # Single forward pass: [N, 3, 160, 160] → [N, 512]
        batch = torch.cat(tensors, dim=0)

        with torch.no_grad():
            embeddings = self.model(batch)

        embeddings_np = embeddings.cpu().numpy()

        # L2 normalize each row (for cosine similarity via inner product)
        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)  # avoid division by zero
        embeddings_np = embeddings_np / norms

        return embeddings_np

    def decode_base64_image(self, base64_string: str, validate_size: bool = True) -> Image.Image:
        """
        Decode Base64 image string to PIL Image

        Args:
            base64_string: Base64-encoded image
            validate_size: If True, validate image size before decode (prevents DoS)

        Returns:
            PIL Image

        Raises:
            ValueError: If decoding fails or validation fails
        """
        try:
            # Validate Base64 string length before decode (prevent memory attacks)
            if validate_size and len(base64_string) > 15_000_000:  # ~10MB encoded
                raise ValueError(
                    f"Base64 image too large: {len(base64_string)} bytes "
                    "(max 15MB encoded / ~10MB decoded)"
                )

            # Remove data URL prefix if present
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            # Decode Base64
            try:
                image_bytes = base64.b64decode(base64_string, validate=True)
            except Exception as e:
                raise ValueError(f"Invalid Base64 encoding: {e}")

            # Validate decoded size
            if validate_size and len(image_bytes) > 10_000_000:  # 10MB decoded
                raise ValueError(
                    f"Decoded image too large: {len(image_bytes)} bytes (max 10MB)"
                )

            # Open as PIL Image
            try:
                image = Image.open(io.BytesIO(image_bytes))
            except Exception as e:
                raise ValueError(f"Invalid image format: {e}")

            # Validate image format (ensure JPEG or PNG)
            if image.format not in ['JPEG', 'PNG']:
                raise ValueError(f"Unsupported image format: {image.format} (expected JPEG or PNG)")

            # Validate image dimensions (prevent extreme sizes)
            width, height = image.size
            min_dim = self.image_size  # 160 — matches FaceNet input requirement
            if width < min_dim or height < min_dim:
                raise ValueError(
                    f"Image too small: {width}x{height}, minimum {min_dim}x{min_dim} required"
                )
            if width > 4096 or height > 4096:
                raise ValueError(f"Image too large: {width}x{height} (maximum 4096x4096)")

            return image

        except ValueError:
            # Re-raise ValueError with original message
            raise
        except Exception as e:
            logger.error(f"Failed to decode Base64 image: {e}")
            raise ValueError(f"Image decoding failed: {e}")

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings

        Args:
            embedding1: First embedding (512-dim)
            embedding2: Second embedding (512-dim)

        Returns:
            Cosine similarity score [0, 1]
        """
        # Cosine similarity (embeddings are already L2-normalized)
        similarity = np.dot(embedding1, embedding2)
        return float(similarity)

    def is_match(self, embedding1: np.ndarray, embedding2: np.ndarray, threshold: float = None) -> bool:
        """
        Check if two embeddings represent the same person

        Args:
            embedding1: First embedding
            embedding2: Second embedding
            threshold: Similarity threshold (default from settings)

        Returns:
            True if embeddings match
        """
        if threshold is None:
            threshold = settings.RECOGNITION_THRESHOLD

        similarity = self.compute_similarity(embedding1, embedding2)
        return similarity >= threshold


# Global model instance (initialized in startup)
facenet_model = FaceNetModel()
