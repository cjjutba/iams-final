# InsightFace Unified Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace FaceNet + MTCNN + MediaPipe with InsightFace (ArcFace + SCRFD) so registration and CCTV recognition use an identical preprocessing chain, eliminating the domain gap that causes "No students detected."

**Architecture:** One `InsightFaceModel` class wraps `insightface.app.FaceAnalysis` (buffalo_l). It is shared across registration (`face_service.py`) and CCTV recognition (`recognition_service.py`, `live_stream_service.py`). Because SCRFD detection + 5-point alignment + ArcFace embedding run identically on both selfie uploads and live frames, embeddings are geometrically compatible and cosine similarity is meaningful.

**Tech Stack:** `insightface>=0.7.3`, `onnxruntime>=1.21.0`, ONNX Runtime CoreML provider (Apple Silicon), FAISS `IndexFlatIP` 512-dim (unchanged), FastAPI (unchanged), React Native mobile (unchanged).

---

## Task 1: Update Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Edit requirements.txt — remove old ML stack, add InsightFace**

In `backend/requirements.txt`, find the `# ===== ML / Face Recognition =====` section and replace it entirely:

```
# ===== ML / Face Recognition =====
insightface>=0.7.3
onnxruntime>=1.21.0
faiss-cpu==1.13.2
numpy==2.4.2
pillow==12.1.0
opencv-python-headless==4.13.0.90
```

Lines removed: `torch==2.10.0+cpu`, `torchvision==0.25.0+cpu`, `facenet-pytorch==2.6.0`, `mediapipe>=0.10.14`

**Step 2: Install the new dependencies**

```bash
cd backend
source venv/bin/activate   # or: venv\Scripts\activate on Windows
pip uninstall -y torch torchvision facenet-pytorch mediapipe
pip install insightface>=0.7.3 onnxruntime>=1.21.0
```

Expected: no errors. InsightFace downloads model files (~500MB) on first use, not at install time.

**Step 3: Verify imports**

```bash
python -c "import insightface; import onnxruntime; print('OK', onnxruntime.get_available_providers())"
```

Expected output includes `CoreMLExecutionProvider` on macOS, `CPUExecutionProvider` everywhere.

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "build: replace FaceNet+MediaPipe with insightface+onnxruntime"
```

---

## Task 2: Write Failing Tests for InsightFaceModel

**Files:**
- Create: `backend/tests/unit/test_insightface_model.py`

**Step 1: Write the full test file**

Create `backend/tests/unit/test_insightface_model.py`:

```python
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

            assert m.app is not None
            mock_instance.prepare.assert_called_once()

    def test_load_model_raises_on_import_error(self):
        """RuntimeError raised if insightface is not installed."""
        with patch.dict("sys.modules", {"insightface": None, "insightface.app": None}):
            from app.services.ml.insightface_model import InsightFaceModel
            m = InsightFaceModel()
            m.app = None
            with pytest.raises(RuntimeError, match="not loaded"):
                m.get_embedding(Image.new("RGB", (200, 200)))


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
        """PIL Image → 512-dim L2-normalized embedding."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        img = Image.new("RGB", (200, 200), color="blue")
        emb = model_with_mock_app.get_embedding(img)
        assert emb.shape == (512,)
        assert abs(np.linalg.norm(emb) - 1.0) < 1e-5

    def test_returns_512_dim_normalized_from_bytes(self, model_with_mock_app):
        """JPEG bytes → 512-dim L2-normalized embedding."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        emb = model_with_mock_app.get_embedding(_make_jpeg_bytes())
        assert emb.shape == (512,)
        assert abs(np.linalg.norm(emb) - 1.0) < 1e-5

    def test_returns_512_dim_normalized_from_ndarray(self, model_with_mock_app):
        """BGR numpy array → 512-dim L2-normalized embedding."""
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
        # Should return face1 (first = largest in InsightFace ordering)
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
        """3 images → [3, 512] array."""
        model_with_mock_app.app.get.return_value = [_make_mock_face()]
        images = [Image.new("RGB", (200, 200)) for _ in range(3)]
        result = model_with_mock_app.get_embeddings_batch(images)
        assert result.shape == (3, 512)

    def test_skips_images_with_no_face(self, model_with_mock_app):
        """Images with no face are skipped; remaining embeddings returned."""
        # First call: face found; second: no face; third: face found
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
# Tests: decode_base64_image (security validation, same as old FaceNetModel)
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
```

**Step 2: Run tests — confirm they all FAIL with ImportError**

```bash
cd backend
pytest tests/unit/test_insightface_model.py -v
```

Expected: `ImportError: cannot import name 'InsightFaceModel' from 'app.services.ml.insightface_model'` (module doesn't exist yet).

---

## Task 3: Implement InsightFaceModel

**Files:**
- Create: `backend/app/services/ml/insightface_model.py`

**Step 1: Write the implementation**

Create `backend/app/services/ml/insightface_model.py`:

```python
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
from dataclasses import dataclass, field
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
        Single image → 512-dim L2-normalized ArcFace embedding.

        Used by face_service.py for each image during registration.
        SCRFD detects the face; ArcFace embeds the aligned 112×112 crop.

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
        List of images → [N, 512] L2-normalized embeddings.

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
        BGR frame → list of DetectedFace with bbox + ArcFace embedding.

        Single call replaces the old two-step pipeline:
          MediaPipe detect  →  face crop  →  FaceNet embed

        Now:
          SCRFD detect + 5-pt align + ArcFace embed  (one app.get() call)

        The same SCRFD + ArcFace instance used here is also used for
        registration, so embeddings are numerically compatible.

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
            for face in insight_faces:
                x1, y1, x2, y2 = face.bbox.astype(int)
                result.append(
                    DetectedFace(
                        x=max(0, x1),
                        y=max(0, y1),
                        width=max(1, x2 - x1),
                        height=max(1, y2 - y1),
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
```

**Step 2: Run tests — confirm they now PASS**

```bash
cd backend
pytest tests/unit/test_insightface_model.py -v
```

Expected: all tests PASS.

**Step 3: Commit**

```bash
git add backend/app/services/ml/insightface_model.py backend/tests/unit/test_insightface_model.py
git commit -m "feat(ml): add InsightFaceModel with ArcFace+SCRFD (buffalo_l)"
```

---

## Task 4: Update config.py

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Remove old ML settings, add InsightFace settings**

In `backend/app/config.py`, find the `# Face Recognition` section and replace it:

**Remove these lines:**
```python
USE_FACE_ALIGNMENT: bool = True  # Enable MTCNN face alignment before embedding
USE_FACE_ALIGNMENT_FOR_RECOGNITION: bool = True  # Run MTCNN on the 20%-padded MediaPipe crop
FACE_IMAGE_SIZE: int = 160  # FaceNet input size (160x160)
MEDIAPIPE_DETECTION_CONFIDENCE: float = 0.35  # Min confidence for face detection
RECOGNITION_MIN_FACE_PX: int = 40  # Minimum face crop dimension (px)
```

**Add these lines** (after `RECOGNITION_TOP_K`):
```python
INSIGHTFACE_MODEL: str = "buffalo_l"    # InsightFace model pack (SCRFD + ArcFace ResNet50)
INSIGHTFACE_DET_SIZE: int = 640         # SCRFD input resolution (square)
```

**Step 2: Verify settings load without error**

```bash
cd backend
python -c "from app.config import settings; print(settings.INSIGHTFACE_MODEL, settings.INSIGHTFACE_DET_SIZE)"
```

Expected: `buffalo_l 640`

**Step 3: Update config_defaults test to reflect new settings**

In `backend/tests/unit/test_config_defaults.py`, remove assertions for the deleted settings and add assertions for the new ones:

```python
# Remove any assertions for:
#   USE_FACE_ALIGNMENT, USE_FACE_ALIGNMENT_FOR_RECOGNITION,
#   FACE_IMAGE_SIZE, MEDIAPIPE_DETECTION_CONFIDENCE, RECOGNITION_MIN_FACE_PX

# Add:
def test_insightface_defaults():
    from app.config import Settings
    s = Settings()
    assert s.INSIGHTFACE_MODEL == "buffalo_l"
    assert s.INSIGHTFACE_DET_SIZE == 640
```

**Step 4: Run config tests**

```bash
pytest tests/unit/test_config_defaults.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/unit/test_config_defaults.py
git commit -m "feat(config): add InsightFace settings, remove MTCNN/MediaPipe settings"
```

---

## Task 5: Update face_service.py

**Files:**
- Modify: `backend/app/services/face_service.py`

There are 5 call sites to update. Open the file and make the following changes:

**Step 1: Update the import (line 16)**

Change:
```python
from app.services.ml.face_recognition import facenet_model
```
To:
```python
from app.services.ml.insightface_model import insightface_model
```

**Step 2: Update the instance attribute (line 28)**

Change:
```python
self.facenet = facenet_model
```
To:
```python
self.facenet = insightface_model
```

**Step 3: Update generate_embedding calls (lines 88 and 162)**

Both read:
```python
embedding = self.facenet.generate_embedding(image_bytes)
```
Change both to:
```python
embedding = self.facenet.get_embedding(image_bytes)
```

**Step 4: Update the edge API decode call (line 197)**

Change:
```python
pil_img = facenet_model.decode_base64_image(img_bytes)
```
To:
```python
pil_img = insightface_model.decode_base64_image(img_bytes)
```

**Step 5: Update the batch call (line 210)**

Change:
```python
embeddings = facenet_model.generate_embeddings_batch(decoded_images)
```
To:
```python
embeddings = insightface_model.get_embeddings_batch(decoded_images)
```

**Step 6: Run face_service tests**

```bash
pytest tests/unit/test_face_service.py -v
```

Fix any failures (likely import-related). Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/services/face_service.py
git commit -m "feat(face-service): switch from FaceNet to InsightFaceModel"
```

---

## Task 6: Update live_stream_service.py

**Files:**
- Modify: `backend/app/services/live_stream_service.py`

This service has `_create_face_detector()` (module-level), `_detect_faces()`, `_recognise_faces()`, and `_ensure_detector()` — all to be removed or replaced.

**Step 1: Remove the module-level `_create_face_detector()` function**

Find and delete the entire function (approx lines 65–93):
```python
def _create_face_detector():
    ...
```

**Step 2: Update `LiveStreamService.__init__` — remove detector fields**

Change:
```python
self._face_detector = None
self._detector_initialized = False
self._facenet = None
self._faiss = None
self._ml_available = False
self._ml_checked = False
```
To:
```python
self._insight = None
self._faiss = None
self._ml_available = False
self._ml_checked = False
```

**Step 3: Delete `_ensure_detector()` method entirely**

**Step 4: Replace `_ensure_ml()`**

Change the entire method body:
```python
def _ensure_ml(self):
    """Lazy-init InsightFace + FAISS (first call only)."""
    if not self._ml_checked:
        try:
            from app.services.ml.insightface_model import insightface_model
            from app.services.ml.faiss_manager import faiss_manager

            if insightface_model.app is not None and faiss_manager.index is not None:
                self._insight = insightface_model
                self._faiss = faiss_manager
                self._ml_available = True
                logger.info("Live stream: InsightFace + FAISS ready for recognition.")
            else:
                logger.warning(
                    "Live stream: InsightFace/FAISS not loaded — recognition disabled."
                )
        except Exception as exc:
            logger.warning(f"Live stream: ML import failed — recognition disabled: {exc}")
        self._ml_checked = True
```

**Step 5: Update `_process_frame()` — replace the 2-step detect+recognise**

Find in `_process_frame()`:
```python
# 2. Detect faces (only on detection frames)
if run_detection:
    detections = self._detect_faces(frame)
    # 3. Recognise (if ML available)
    if self._ml_available and detections:
        self._recognise_faces(frame, detections)
else:
    detections = cached_detections
```

Replace with:
```python
# 2 & 3. Detect + recognise in one InsightFace call
if run_detection:
    detections = self._detect_and_recognise(frame) if self._ml_available else []
else:
    detections = cached_detections
```

**Step 6: Remove `_detect_faces()` and `_recognise_faces()` methods entirely**

**Step 7: Add `_detect_and_recognise()` method**

Add this new method after `_process_frame`:

```python
def _detect_and_recognise(self, frame: np.ndarray) -> List[Detection]:
    """
    Run InsightFace detection + ArcFace embedding + FAISS search on one frame.
    Returns Detection list (user_id/similarity populated for matched faces).
    """
    try:
        insight_faces = self._insight.get_faces(frame)
        detections = []
        for face in insight_faces:
            user_id, similarity = None, None
            if self._faiss is not None:
                matches = self._faiss.search(face.embedding, k=1)
                if matches:
                    user_id, similarity = matches[0]

            detections.append(Detection(
                x=face.x,
                y=face.y,
                width=face.width,
                height=face.height,
                confidence=face.confidence,
                user_id=user_id,
                similarity=similarity,
            ))
        return detections
    except Exception as exc:
        logger.error(f"Live stream detect+recognise error: {exc}")
        return []
```

**Step 8: Update the stream start call — remove `_ensure_detector()`**

Find where `_ensure_detector()` is called (approx line 351):
```python
self._ensure_detector()
self._ensure_ml()
```
Replace with:
```python
self._ensure_ml()
```

**Step 9: Run live stream tests**

```bash
pytest tests/unit/test_live_stream_webrtc_mode.py -v
```

Fix any failures (likely mock references to `_face_detector` or `_create_face_detector`). Expected: PASS.

**Step 10: Commit**

```bash
git add backend/app/services/live_stream_service.py
git commit -m "feat(live-stream): replace MediaPipe+FaceNet with InsightFace unified pipeline"
```

---

## Task 7: Update recognition_service.py

**Files:**
- Modify: `backend/app/services/recognition_service.py`

**Step 1: Update `__init__` — remove detector fields**

Change:
```python
self._face_detector = None
self._detector_initialized = False
self._facenet = None
self._faiss = None
self._ml_available = False
self._ml_checked = False
```
To:
```python
self._insight = None
self._faiss = None
self._ml_available = False
self._ml_checked = False
```

**Step 2: Delete `_ensure_detector()` method entirely**

**Step 3: Replace `_ensure_ml()`**

```python
def _ensure_ml(self):
    if not self._ml_checked:
        try:
            from app.services.ml.insightface_model import insightface_model
            from app.services.ml.faiss_manager import faiss_manager

            if insightface_model.app is not None and faiss_manager.index is not None:
                self._insight = insightface_model
                self._faiss = faiss_manager
                self._ml_available = True
                logger.info("Recognition: InsightFace + FAISS available")
            else:
                logger.warning("Recognition: InsightFace/FAISS not loaded")
        except Exception as exc:
            logger.warning(f"Recognition: ML import failed: {exc}")
        self._ml_checked = True
```

**Step 4: Remove `_detect_faces()` method entirely**

**Step 5: Replace `_recognise_faces_batch()` with `_process_frame_ml()`**

Delete the old `_detect_faces()` and `_recognise_faces_batch()` methods, then add:

```python
def _process_frame_ml(self, frame: np.ndarray) -> tuple:
    """
    Run InsightFace detection + recognition on one frame.
    Returns (detections, frame_width, frame_height).
    """
    h, w = frame.shape[:2]
    max_dim = max(h, w)
    cap = settings.RECOGNITION_MAX_DIM

    if max_dim > cap:
        scale = cap / max_dim
        new_w, new_h = int(w * scale), int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    frame_h, frame_w = frame.shape[:2]

    if not self._ml_available:
        return [], frame_w, frame_h

    try:
        insight_faces = self._insight.get_faces(frame)
        if not insight_faces:
            return [], frame_w, frame_h

        logger.info(
            f"Recognition: detected {len(insight_faces)} face(s) "
            f"in {frame_w}x{frame_h} frame"
        )

        detections = []
        for face in insight_faces:
            user_id, similarity = None, None
            if self._faiss is not None:
                matches = self._faiss.search(face.embedding, k=1)
                if matches:
                    user_id, similarity = matches[0]

            detections.append(Detection(
                x=face.x,
                y=face.y,
                width=face.width,
                height=face.height,
                confidence=face.confidence,
                user_id=user_id,
                similarity=similarity,
            ))
        return detections, frame_w, frame_h

    except Exception as exc:
        logger.error(f"Recognition: InsightFace error: {exc}")
        return [], frame_w, frame_h
```

**Step 6: Update the capture loop call site**

Find in `_capture_loop` (or equivalent method) where `_detect_faces` and `_recognise_faces_batch` are called (approx lines 355–366):

```python
# Old pattern:
detections = self._detect_faces(frame)
if not detections:
    return [], frame_w, frame_h
...
if self._ml_available:
    self._recognise_faces_batch(frame, detections)
return detections, frame_w, frame_h
```

Replace with a single call to `_process_frame_ml`:

```python
return self._process_frame_ml(frame)
```

**Step 7: Update the `start()` method — remove `_ensure_detector()` call**

Find (approx line 149–150):
```python
self._ensure_detector()
self._ensure_ml()
```
Replace with:
```python
self._ensure_ml()
```

Also update the import at the top of the method body — remove the `_create_face_detector` import if it's inline.

**Step 8: Run recognition tests**

```bash
pytest tests/unit/test_recognition_backoff.py -v
```

Fix any failures. Expected: PASS.

**Step 9: Commit**

```bash
git add backend/app/services/recognition_service.py
git commit -m "feat(recognition): replace MediaPipe+FaceNet batch with InsightFace unified call"
```

---

## Task 8: Update main.py Startup

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Update the startup import and load call**

In the `startup_event()` function, find:
```python
from app.services.ml.face_recognition import facenet_model
from app.services.ml.faiss_manager import faiss_manager

logger.info("Loading FaceNet model...")
facenet_model.load_model()
```

Replace with:
```python
from app.services.ml.insightface_model import insightface_model
from app.services.ml.faiss_manager import faiss_manager

logger.info("Loading InsightFace model (buffalo_l)...")
insightface_model.load_model()
```

**Step 2: Update the FAISS reconciliation import (if it references facenet_model)**

Scan the startup block for any remaining `facenet_model` references and update them to `insightface_model`.

**Step 3: Verify the server starts without import errors**

```bash
cd backend
python -c "from app.main import app; print('Import OK')"
```

Expected: `Import OK` (no ImportError for face_recognition or mediapipe).

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(startup): load InsightFace model instead of FaceNet on startup"
```

---

## Task 9: Retire Old Test File + Run Full Suite

**Files:**
- Delete: `backend/tests/unit/test_face_recognition_model.py`

**Step 1: Delete the old FaceNet test file**

```bash
rm backend/tests/unit/test_face_recognition_model.py
```

It tested `FaceNetModel` which no longer exists. `test_insightface_model.py` covers the equivalent behaviors.

**Step 2: Run the full unit test suite**

```bash
cd backend
pytest tests/unit/ -v
```

Fix any remaining failures (likely stray imports of `face_recognition` or `mediapipe` in other test files). Expected: all PASS.

**Step 3: Run integration tests**

```bash
pytest tests/integration/ -v
```

Fix any failures. Expected: all PASS.

**Step 4: Commit**

```bash
git add -u   # stage deletions
git add backend/tests/
git commit -m "test: remove FaceNet tests, verify full suite passes with InsightFace"
```

---

## Task 10: One-Time FAISS Migration

> **Do this before the demo / thesis presentation.** Old FaceNet embeddings are numerically incompatible with ArcFace embeddings.

**Step 1: Stop the backend server**

**Step 2: Delete the old FAISS index**

```bash
rm backend/data/faiss/faces.index
```

**Step 3: Wipe face_registrations in the database**

Connect to Supabase (or local PostgreSQL) and run:

```sql
TRUNCATE face_registrations;
```

**Step 4: Restart the backend**

```bash
cd backend && python run.py
```

Startup will log: `FAISS health check: in sync (0 vectors)` — expected.

**Step 5: Re-register all students**

Each student opens the mobile app and completes the face registration flow (3–5 selfies via `POST /api/v1/face/register`). No mobile app changes are required.

**Step 6: Verify registration works**

After one student re-registers, test recognition:

```bash
curl -X GET http://localhost:8000/api/v1/face/stats
```

Expected: `{"total_vectors": 1, "user_mappings": 1, ...}`

---

## Task 11: Update ml-pipeline-spec.md

**Files:**
- Modify: `docs/main/ml-pipeline-spec.md`

**Step 1: Update the document**

Replace the entire `## 1. Preprocessing Chain` section and `## 2. Face Registration` section to reflect InsightFace. Key changes:

- Section 1.2 Backend: remove MTCNN/FaceNet steps; add SCRFD + 5-pt landmark alignment + ArcFace steps
- Section 2: update registration flow to show `get_embedding()` call
- Section 3: update recognition flow to show `get_faces()` single call
- Section 3.3 Configuration: replace `USE_FACE_ALIGNMENT`, `FACE_IMAGE_SIZE` etc. with `INSIGHTFACE_MODEL`, `INSIGHTFACE_DET_SIZE`
- Section 7.2 Threshold table: remove removed settings; add new ones

**Step 2: Commit**

```bash
git add docs/main/ml-pipeline-spec.md
git commit -m "docs: update ml-pipeline-spec for InsightFace unified pipeline"
```

---

## Completion Checklist

- [ ] `insightface` + `onnxruntime` installed, old deps removed
- [ ] `InsightFaceModel` class created with all tests passing
- [ ] `config.py` has `INSIGHTFACE_MODEL` + `INSIGHTFACE_DET_SIZE`, old settings removed
- [ ] `face_service.py` calls `get_embedding()` / `get_embeddings_batch()`
- [ ] `live_stream_service.py` uses `_detect_and_recognise()` (single InsightFace call)
- [ ] `recognition_service.py` uses `_process_frame_ml()` (single InsightFace call)
- [ ] `main.py` startup loads `insightface_model`
- [ ] All unit + integration tests pass
- [ ] Old FAISS index deleted, `face_registrations` truncated
- [ ] Students re-registered via existing mobile app flow
- [ ] Face visible in CCTV feed → detected + recognized with `user_id`
