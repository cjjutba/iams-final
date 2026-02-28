"""
Unit Tests for FaceNet Model (face_recognition.py)

Tests the FaceNetModel class: device selection, image preprocessing,
embedding generation (with mocked torch model), base64 decoding,
similarity computation, and match checking.

The actual InceptionResnetV1 model is NOT loaded in these tests --
torch inference is mocked to keep tests fast and dependency-free.
"""

import base64
import io

import numpy as np
import pytest
import torch
from PIL import Image
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 160, height: int = 160, color="blue") -> bytes:
    """Create a minimal JPEG image as raw bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_base64_jpeg(width: int = 100, height: int = 100, color="green") -> str:
    """Create a Base64-encoded JPEG string."""
    return base64.b64encode(_make_jpeg_bytes(width, height, color)).decode()


def _make_png_base64(width: int = 100, height: int = 100) -> str:
    """Create a Base64-encoded PNG string."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFaceNetModel:
    """Unit tests for FaceNetModel."""

    # -- Device selection --------------------------------------------------

    def test_get_device_cpu_when_no_cuda(self):
        """Selects CPU device when CUDA is not available."""
        with patch("torch.cuda.is_available", return_value=False):
            from app.services.ml.face_recognition import FaceNetModel
            model = FaceNetModel()
            assert model.device == torch.device("cpu")

    def test_get_device_cpu_when_gpu_disabled(self):
        """Selects CPU device when USE_GPU setting is False, even if
        CUDA is available."""
        with patch("torch.cuda.is_available", return_value=True), \
             patch("app.services.ml.face_recognition.settings") as mock_settings:
            mock_settings.USE_GPU = False
            mock_settings.FACE_IMAGE_SIZE = 160
            from app.services.ml.face_recognition import FaceNetModel
            model = FaceNetModel()
            assert model.device == torch.device("cpu")

    # -- Image preprocessing -----------------------------------------------

    def test_preprocess_pil_image(self):
        """PIL Image is resized to 160x160 and normalized to [-1, 1]."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        img = Image.new("RGB", (200, 200), color="red")
        tensor = model.preprocess_image(img)

        assert tensor.shape == (1, 3, 160, 160)
        assert tensor.min().item() >= -1.0
        assert tensor.max().item() <= 1.0

    def test_preprocess_numpy_array(self):
        """Numpy array (H, W, 3) is converted and preprocessed correctly."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        arr = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        tensor = model.preprocess_image(arr)

        assert tensor.shape == (1, 3, 160, 160)

    def test_preprocess_non_rgb_image(self):
        """RGBA image is converted to RGB before preprocessing."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
        tensor = model.preprocess_image(img)

        # Should be 3 channels (RGB), not 4 (RGBA)
        assert tensor.shape == (1, 3, 160, 160)

    def test_preprocess_grayscale_image(self):
        """Grayscale (L mode) image is converted to RGB."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        img = Image.new("L", (200, 200), color=128)
        tensor = model.preprocess_image(img)

        assert tensor.shape == (1, 3, 160, 160)

    # -- Embedding generation ----------------------------------------------

    def test_generate_embedding_not_loaded(self):
        """Raises RuntimeError when model has not been loaded."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()
        model.model = None

        with pytest.raises(RuntimeError, match="not loaded"):
            model.generate_embedding(Image.new("RGB", (160, 160)))

    def test_generate_embedding_with_mock_model(self):
        """Full pipeline: PIL Image -> preprocess -> mock model -> L2-normalized
        512-dim numpy array."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        # Mock the torch model to return a known 512-dim tensor
        mock_torch_model = MagicMock()
        fake_output = torch.randn(1, 512)
        mock_torch_model.return_value = fake_output
        model.model = mock_torch_model

        img = Image.new("RGB", (160, 160), color="blue")
        embedding = model.generate_embedding(img)

        assert embedding.shape == (512,)
        # Embedding should be L2-normalized (unit vector)
        assert abs(np.linalg.norm(embedding) - 1.0) < 0.01

    def test_generate_embedding_from_bytes(self):
        """Bytes input (JPEG) is decoded into a PIL Image and processed."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        mock_torch_model = MagicMock()
        mock_torch_model.return_value = torch.randn(1, 512)
        model.model = mock_torch_model

        jpeg_bytes = _make_jpeg_bytes()
        embedding = model.generate_embedding(jpeg_bytes)

        assert embedding.shape == (512,)
        assert abs(np.linalg.norm(embedding) - 1.0) < 0.01

    def test_generate_embeddings_batch_not_loaded(self):
        """Batch generation raises RuntimeError when model is not loaded."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()
        model.model = None

        images = [Image.new("RGB", (160, 160))]
        with pytest.raises(RuntimeError, match="not loaded"):
            model.generate_embeddings_batch(images)

    # -- Base64 decoding ---------------------------------------------------

    def test_decode_base64_valid_jpeg(self):
        """Valid Base64 JPEG string is decoded to a PIL Image."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        b64 = _make_base64_jpeg()
        result = model.decode_base64_image(b64)

        assert isinstance(result, Image.Image)
        assert result.format == "JPEG"

    def test_decode_base64_valid_png(self):
        """Valid Base64 PNG string is decoded to a PIL Image."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        b64 = _make_png_base64()
        result = model.decode_base64_image(b64)

        assert isinstance(result, Image.Image)
        assert result.format == "PNG"

    def test_decode_base64_with_data_url_prefix(self):
        """Base64 string with data URL prefix is handled correctly."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        raw_b64 = _make_base64_jpeg()
        data_url = f"data:image/jpeg;base64,{raw_b64}"
        result = model.decode_base64_image(data_url)

        assert isinstance(result, Image.Image)

    def test_decode_base64_invalid_string(self):
        """Invalid Base64 string raises ValueError."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        with pytest.raises(ValueError, match="Invalid Base64"):
            model.decode_base64_image("not_valid_base64!!!")

    def test_decode_base64_too_large(self):
        """Base64 string exceeding 15MB limit raises ValueError."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        # 16MB of valid Base64 characters (exceeds 15MB limit)
        huge = "A" * 16_000_000
        with pytest.raises(ValueError, match="too large"):
            model.decode_base64_image(huge)

    def test_decode_base64_image_too_small(self):
        """Image smaller than 10x10 pixels raises ValueError."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        # Create a tiny 5x5 JPEG
        tiny_b64 = _make_base64_jpeg(width=5, height=5)
        with pytest.raises(ValueError, match="too small"):
            model.decode_base64_image(tiny_b64)

    # -- Similarity computation --------------------------------------------

    def test_compute_similarity_same_vector(self):
        """Cosine similarity of a vector with itself is ~1.0."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        emb = np.ones(512, dtype=np.float32)
        emb = emb / np.linalg.norm(emb)

        sim = model.compute_similarity(emb, emb)
        assert abs(sim - 1.0) < 0.01

    def test_compute_similarity_orthogonal_vectors(self):
        """Cosine similarity of orthogonal vectors is ~0.0."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        rng = np.random.RandomState(42)
        v1 = rng.randn(512).astype(np.float32)
        v1 = v1 / np.linalg.norm(v1)

        v2 = rng.randn(512).astype(np.float32)
        v2 = v2 - np.dot(v2, v1) * v1
        v2 = v2 / np.linalg.norm(v2)

        sim = model.compute_similarity(v1, v2)
        assert abs(sim) < 0.01

    # -- Match checking ----------------------------------------------------

    def test_is_match_true(self):
        """is_match returns True when similarity exceeds threshold."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        emb = np.ones(512, dtype=np.float32)
        emb = emb / np.linalg.norm(emb)

        assert model.is_match(emb, emb, threshold=0.6) is True

    def test_is_match_false(self):
        """is_match returns False when similarity is below threshold."""
        from app.services.ml.face_recognition import FaceNetModel
        model = FaceNetModel()

        rng = np.random.RandomState(42)
        v1 = rng.randn(512).astype(np.float32)
        v1 = v1 / np.linalg.norm(v1)

        v2 = rng.randn(512).astype(np.float32)
        v2 = v2 - np.dot(v2, v1) * v1
        v2 = v2 / np.linalg.norm(v2)

        assert model.is_match(v1, v2, threshold=0.6) is False
