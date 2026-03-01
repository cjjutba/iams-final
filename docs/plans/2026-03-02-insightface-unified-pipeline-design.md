# InsightFace Unified Pipeline Design

**Date:** 2026-03-02
**Status:** Approved
**Scope:** Replace FaceNet + MTCNN + MediaPipe with InsightFace (ArcFace + SCRFD) across the entire face recognition pipeline.

---

## Problem Statement

The current pipeline has a fundamental **domain gap**:

- **Registration path:** Mobile front camera selfie (close-up, good lighting) → MTCNN alignment → FaceNet embedding
- **Recognition path:** CCTV frame (wide-angle, distant, variable lighting) → MediaPipe detection → FaceNet embedding

Because the two inputs pass through different detectors with different preprocessing, the resulting embeddings are geometrically inconsistent — the cosine similarity between a registration embedding and a live recognition embedding is systematically lower than it should be, causing missed detections even when the student is clearly visible.

---

## Solution: One Model, One Preprocessing Chain

Use **InsightFace** (`buffalo_l` model pack) for both paths. A single `FaceAnalysis.get(image)` call runs SCRFD detection → 5-point landmark alignment → ArcFace ResNet50 embedding identically regardless of input source. When both registration and recognition use the exact same preprocessing, the embeddings are geometrically compatible and cosine similarity scores are meaningful.

---

## Architecture

### Registration Path

```
Mobile (3–5 selfies)
  → POST /api/v1/face/register (multipart — no API change)
  → InsightFaceModel.get_embedding(image)
       → SCRFD 10G detection
       → 5-point landmark alignment → 112×112 aligned crop
       → ArcFace ResNet50 → 512-dim embedding (L2-normalized internally)
  → Average embeddings → L2 normalize
  → FAISS IndexFlatIP.add()    ← same index, same 512-dim, no change
  → DB: face_registrations     ← same table, no schema change
```

### Recognition Path (CCTV)

```
RTSP frame (sampled at 2 FPS by recognition_service.py)
  → InsightFaceModel.get_faces(frame)     ← one call replaces MediaPipe + FaceNet
       → SCRFD batch detection (same model as registration)
       → 5-point alignment per face (same as registration)
       → ArcFace ResNet50 batch embedding (same model as registration)
  → For each DetectedFace:
       → FAISS.search(embedding, k=1)     ← same search, same threshold logic
       → Attach user_id + similarity
  → Push via WebSocket                    ← same message format, no mobile changes
```

---

## Model Selection

**Model pack:** `buffalo_l`

| Component | Model | Paper |
|---|---|---|
| Face detector | SCRFD 10G (ResNet50 backbone) | Guo et al., ICCV 2021 |
| Face recognition | ArcFace w600k_r50 (ResNet50) | Deng et al., CVPR 2019 |
| Alignment | 5-point landmark transform | Baked into InsightFace |
| Embedding dim | 512 | — |

**Why `buffalo_l` over `buffalo_sc`:** ResNet50 backbone for both detector and recognizer gives best accuracy. On M5 MacBook Pro with CoreML execution provider, inference speed is well within real-time requirements for 1 camera at 2 FPS recognition.

---

## Apple Silicon Optimization

InsightFace uses ONNX Runtime. On Apple Silicon (M1/M2/M3/M4/M5), ONNX Runtime supports `CoreMLExecutionProvider` which delegates inference to the Neural Engine and Metal GPU — significantly faster than CPU-only execution.

```python
providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
app = FaceAnalysis(name='buffalo_l', providers=providers)
```

Fallback order: CoreML → CPU. On non-Apple machines, only `CPUExecutionProvider` is used.

---

## New `InsightFaceModel` Class

**File:** `backend/app/services/ml/insightface_model.py`

### Public Interface

```python
class InsightFaceModel:

    def load_model(self) -> None:
        """Load buffalo_l with CoreML on Apple Silicon, CPU elsewhere."""

    def get_embedding(self, image) -> np.ndarray:
        """
        Single image (PIL / np.ndarray / bytes) → 512-dim L2-normalized embedding.
        Raises ValueError if no face detected.
        Used by: face_service.py (registration)
        """

    def get_embeddings_batch(self, images: list) -> np.ndarray:
        """
        List of images → [N, 512] L2-normalized embeddings.
        Used by: face_service.py (batch registration path)
        """

    def get_faces(self, frame: np.ndarray) -> list[DetectedFace]:
        """
        BGR frame → list of DetectedFace with bbox + embedding.
        One call replaces MediaPipe detect + FaceNet embed.
        Used by: recognition_service.py, live_stream_service.py
        """

    def decode_base64_image(self, b64: str, validate_size: bool = True) -> Image.Image:
        """Preserved from FaceNetModel — same validation logic."""
```

### `DetectedFace` Dataclass

```python
@dataclass
class DetectedFace:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    embedding: np.ndarray   # 512-dim, L2-normalized
    user_id: str | None = None
    similarity: float = 0.0
```

Mirrors the existing `Detection` shape so downstream WebSocket push code is unchanged.

---

## Files Changed

### New / Replaced

| File | Action |
|---|---|
| `backend/app/services/ml/insightface_model.py` | **New** — replaces `face_recognition.py` |

### Modified

| File | Change |
|---|---|
| `backend/requirements.txt` | Add `insightface>=0.7.3`, `onnxruntime>=1.21.0`; remove `facenet-pytorch`, `mediapipe`, `torch`, `torchvision` |
| `backend/app/config.py` | Remove MTCNN/MediaPipe settings; add `INSIGHTFACE_MODEL: str = "buffalo_l"`, `INSIGHTFACE_DET_SIZE: int = 640` |
| `backend/app/services/face_service.py` | Update import + 2 call sites (`generate_embedding` → `get_embedding`, `generate_embeddings_batch` → `get_embeddings_batch`) |
| `backend/app/services/recognition_service.py` | Replace `_create_face_detector()` + `_recognise_faces_batch()` with single `model.get_faces()` call |
| `backend/app/services/live_stream_service.py` | Replace `_create_face_detector()` + `_recognise_faces()` with single `model.get_faces()` call |
| `backend/app/main.py` | Update startup import to `insightface_model` |
| `docs/main/ml-pipeline-spec.md` | Update to reflect new pipeline |

### Not Changed

- All routers (`face.py`, `live_stream.py`, `webrtc.py`, `websocket.py`, etc.)
- All Pydantic schemas
- All SQLAlchemy models
- Database schema — zero migrations required
- FAISS index format (`IndexFlatIP`, 512-dim) — same
- Mobile app — zero changes
- WebSocket message format — zero changes
- `faiss_manager.py` — zero changes

---

## Dependency Changes

**Removed:**
- `torch` / `torchvision` (~2GB, no longer needed — InsightFace uses ONNX Runtime)
- `facenet-pytorch` (FaceNet + MTCNN)
- `mediapipe` (face detection)

**Added:**
- `insightface>=0.7.3` (SCRFD + ArcFace, ONNX-based)
- `onnxruntime>=1.21.0` (CPU + CoreML execution providers)

Net result: simpler install, ~2GB smaller, no MPS/CUDA version conflicts.

---

## One-Time Migration (Re-registration)

ArcFace embeddings are numerically incompatible with FaceNet embeddings. The FAISS index and `face_registrations` table must be reset once, then all students re-register via the existing mobile flow.

**Steps (run before demo):**

```bash
# 1. Delete old FAISS index
rm backend/data/faiss/faces.index

# 2. Wipe face registrations in DB
# SQL: TRUNCATE face_registrations;

# 3. Restart backend — creates fresh empty FAISS index on startup

# 4. Students re-register via existing mobile app flow
#    POST /api/v1/face/register — no changes needed
```

For ≤50 students, this is a single session operation.

---

## Configuration Changes

**Removed settings:**
```python
# Removed (MTCNN / MediaPipe specific)
USE_FACE_ALIGNMENT: bool
USE_FACE_ALIGNMENT_FOR_RECOGNITION: bool
MEDIAPIPE_DETECTION_CONFIDENCE: float
RECOGNITION_MIN_FACE_PX: int
FACE_IMAGE_SIZE: int
```

**Added settings:**
```python
INSIGHTFACE_MODEL: str = "buffalo_l"     # Model pack name
INSIGHTFACE_DET_SIZE: int = 640          # SCRFD input resolution
```

**Unchanged settings:**
```python
RECOGNITION_THRESHOLD: float = 0.45     # Cosine similarity threshold
RECOGNITION_MARGIN: float = 0.1         # Min gap top-1 vs top-2
RECOGNITION_TOP_K: int = 3              # FAISS neighbors
RECOGNITION_FPS: float = 2.0            # Frame sampling rate
FAISS_INDEX_PATH: str = "data/faiss/faces.index"
```

---

## Thesis Citation Table

| Component | Citation |
|---|---|
| ArcFace | Deng, J. et al. "ArcFace: Additive Angular Margin Loss for Deep Face Recognition." CVPR 2019. |
| SCRFD | Guo, J. et al. "Sample and Computation Redistribution for Efficient Face Detection." ICCV 2021. |
| InsightFace | Deng, J. et al. "InsightFace: An Open Source 2D&3D Deep Face Analysis Library." 2022. |
| FAISS | Johnson, J. et al. "Billion-Scale Similarity Search with GPUs." IEEE TPAMI 2021. |

---

## Success Criteria

- Student registers via existing mobile flow (3–5 selfies)
- Face visible in CCTV live feed → detected and recognized with `user_id` attached
- Recognition works at 2 FPS without lag on M5 MacBook Pro
- Cosine similarity scores for matched students consistently above 0.45 threshold
- "No students detected" no longer appears when a registered student is in frame
