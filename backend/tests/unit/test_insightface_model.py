"""
Unit tests for InsightFaceModel (insightface_model.py).

FaceAnalysis is mocked — no model download required in tests.
Tests verify: load_model, get_embedding, get_embeddings_batch,
get_faces, decode_base64_image.
"""
import base64
import io
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 200, height: int = 200, color="blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_b64_jpeg(width: int = 200, height: int = 200) -> str:
    return base64.b64encode(_make_jpeg_bytes(width, height)).decode()


def _make_b64_png(width: int = 200, height: int = 200) -> str:
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_mock_face(bbox=(100, 150, 200, 250), score=0.95, emb_dim=512):
    """Return a mock InsightFace Face object."""
    face = MagicMock()
    face.bbox = np.array(bbox, dtype=np.float32)
    face.det_score = score
    normed = np.ones(emb_dim, dtype=np.float32)
    normed /= np.linalg.norm(normed)
    face.normed_embedding = normed
    return face


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def model_with_mock_app():
    """InsightFaceModel with a mocked FaceAnalysis app."""
    from app.services.ml.insightface_model import InsightFaceModel
    m = InsightFaceModel()
    m.app = MagicMock()
    return m


# ---------------------------------------------------------------------------
# Tests: load_model
# ---------------------------------------------------------------------------

class TestLoadModel:
    def test_load_model_sets_app(self):
        """load_model() initializes self.app."""
        with patch("insightface.app.FaceAnalysis") as mock_fa:
            mock_instance = MagicMock()
            mock_fa.return_value = mock_instance

            from app.services.ml.insightface_model import InsightFaceModel
            m = InsightFaceModel()
            m.load_model()

            assert m.app is mock_instance
            mock_instance.prepare.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: get_embedding
# ---------------------------------------------------------------------------

class TestGetEmbedding:
    def test_raises_if_not_loaded(self):
        """get_embedding raises RuntimeError when app is None."""
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        m.app = None
        with pytest.raises(RuntimeError, match="not loaded"):
            m.get_embedding(Image.new("RGB", (200, 200)))

    def test_returns_512_dim_normalized_from_pil(self, model_with_mock_app):
        """PIL Image -> 512-dim L2-normalized embedding."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        img = Image.new("RGB", (200, 200), color="blue")
        emb = model_with_mock_app.get_embedding(img)
        assert emb.shape == (512,)
        assert abs(np.linalg.norm(emb) - 1.0) < 1e-5

    def test_returns_512_dim_normalized_from_bytes(self, model_with_mock_app):
        """JPEG bytes -> 512-dim L2-normalized embedding."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        emb = model_with_mock_app.get_embedding(_make_jpeg_bytes())
        assert emb.shape == (512,)
        assert abs(np.linalg.norm(emb) - 1.0) < 1e-5

    def test_returns_512_dim_normalized_from_ndarray(self, model_with_mock_app):
        """BGR numpy array -> 512-dim L2-normalized embedding."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        emb = model_with_mock_app.get_embedding(frame)
        assert emb.shape == (512,)

    def test_raises_if_no_face_detected(self, model_with_mock_app):
        """ValueError raised when InsightFace finds no face."""
        model_with_mock_app.app.get.return_value = []
        with pytest.raises(ValueError, match="No face detected"):
            model_with_mock_app.get_embedding(Image.new("RGB", (200, 200)))

    def test_takes_largest_face_when_multiple(self, model_with_mock_app):
        """First face returned by InsightFace (largest) is used."""
        face1 = _make_mock_face()
        face1.normed_embedding = np.full(512, 0.1, dtype=np.float32)
        face1.normed_embedding /= np.linalg.norm(face1.normed_embedding)

        face2 = _make_mock_face()
        face2.normed_embedding = np.full(512, 0.9, dtype=np.float32)
        face2.normed_embedding /= np.linalg.norm(face2.normed_embedding)

        model_with_mock_app.app.get.return_value = [face1, face2]
        emb = model_with_mock_app.get_embedding(Image.new("RGB", (200, 200)))
        assert np.allclose(emb, face1.normed_embedding, atol=1e-5)


# ---------------------------------------------------------------------------
# Tests: get_embeddings_batch
# ---------------------------------------------------------------------------

class TestGetEmbeddingsBatch:
    def test_raises_if_not_loaded(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        m.app = None
        with pytest.raises(RuntimeError, match="not loaded"):
            m.get_embeddings_batch([Image.new("RGB", (200, 200))])

    def test_returns_n_512_array(self, model_with_mock_app):
        """3 images -> [3, 512] array."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        images = [Image.new("RGB", (200, 200)) for _ in range(3)]
        result = model_with_mock_app.get_embeddings_batch(images)
        assert result.shape == (3, 512)

    def test_skips_images_with_no_face(self, model_with_mock_app):
        """Images with no face are skipped; remaining embeddings returned."""
        model_with_mock_app.app.get.side_effect = [
            [_make_mock_face()],
            [],
            [_make_mock_face()],
        ]
        images = [Image.new("RGB", (200, 200)) for _ in range(3)]
        result = model_with_mock_app.get_embeddings_batch(images)
        assert result.shape == (2, 512)

    def test_raises_if_all_images_have_no_face(self, model_with_mock_app):
        model_with_mock_app.app.get.return_value = []
        with pytest.raises(ValueError, match="No valid embeddings"):
            model_with_mock_app.get_embeddings_batch([Image.new("RGB", (200, 200))])


# ---------------------------------------------------------------------------
# Tests: get_faces
# ---------------------------------------------------------------------------

class TestGetFaces:
    def test_returns_empty_if_not_loaded(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        m.app = None
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert m.get_faces(frame) == []

    def test_returns_empty_when_no_faces(self, model_with_mock_app):
        model_with_mock_app.app.get.return_value = []
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert model_with_mock_app.get_faces(frame) == []

    def test_returns_detected_face_fields(self, model_with_mock_app):
        """DetectedFace has correct bbox, confidence, and embedding."""
        from app.services.ml.insightface_model import DetectedFace
        model_with_mock_app.app.get.return_value = [
            _make_mock_face(bbox=(100, 150, 200, 250), score=0.95)
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        faces = model_with_mock_app.get_faces(frame)

        assert len(faces) == 1
        f = faces[0]
        assert isinstance(f, DetectedFace)
        assert f.x == 100
        assert f.y == 150
        assert f.width == 100   # 200 - 100
        assert f.height == 100  # 250 - 150
        assert f.confidence == pytest.approx(0.95)
        assert f.embedding.shape == (512,)
        assert f.user_id is None
        assert f.similarity is None

    def test_returns_multiple_faces(self, model_with_mock_app):
        model_with_mock_app.app.get.return_value = [
            _make_mock_face(bbox=(10, 10, 80, 80)),
            _make_mock_face(bbox=(300, 100, 400, 200)),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        faces = model_with_mock_app.get_faces(frame)
        assert len(faces) == 2

    def test_clamps_negative_bbox(self, model_with_mock_app):
        """Negative bbox coordinates are clamped to 0."""
        model_with_mock_app.app.get.return_value = [
            _make_mock_face(bbox=(-5, -10, 100, 120))
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        faces = model_with_mock_app.get_faces(frame)
        assert faces[0].x == 0
        assert faces[0].y == 0


# ---------------------------------------------------------------------------
# Tests: decode_base64_image
# ---------------------------------------------------------------------------

class TestDecodeBase64Image:
    def test_valid_jpeg(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        result = m.decode_base64_image(_make_b64_jpeg())
        assert isinstance(result, Image.Image)
        assert result.format == "JPEG"

    def test_valid_png(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        result = m.decode_base64_image(_make_b64_png())
        assert isinstance(result, Image.Image)
        assert result.format == "PNG"

    def test_data_url_prefix_stripped(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        b64 = f"data:image/jpeg;base64,{_make_b64_jpeg()}"
        result = m.decode_base64_image(b64)
        assert isinstance(result, Image.Image)

    def test_invalid_base64_raises(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        with pytest.raises(ValueError, match="Invalid Base64"):
            m.decode_base64_image("not_valid_base64!!!")

    def test_too_large_raises(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        with pytest.raises(ValueError, match="too large"):
            m.decode_base64_image("A" * 16_000_000)

    def test_image_too_small_raises(self):
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        with pytest.raises(ValueError, match="too small"):
            m.decode_base64_image(_make_b64_jpeg(width=50, height=50))

    def test_decoded_too_large_raises(self):
        """Decoded image > 10MB raises ValueError."""
        from app.services.ml.insightface_model import InsightFaceModel
        from unittest.mock import patch
        m = InsightFaceModel()
        # Patch base64.b64decode to return a 11MB bytestring
        with patch("app.services.ml.insightface_model.base64.b64decode", return_value=b"x" * 11_000_000):
            with pytest.raises(ValueError, match="too large"):
                m.decode_base64_image("dGVzdA==")  # valid base64

    def test_image_too_large_dimensions_raises(self):
        """Image with dimensions > 4096x4096 raises ValueError."""
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        # Create a 4097x4097 image
        img = Image.new("RGB", (4097, 4097), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        with pytest.raises(ValueError, match="too large"):
            m.decode_base64_image(b64)

    def test_unsupported_format_raises(self):
        """BMP image raises ValueError (only JPEG and PNG accepted)."""
        from app.services.ml.insightface_model import InsightFaceModel
        m = InsightFaceModel()
        img = Image.new("RGB", (200, 200), color="white")
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        b64 = base64.b64encode(buf.getvalue()).decode()
        with pytest.raises(ValueError, match="Unsupported image format"):
            m.decode_base64_image(b64)
