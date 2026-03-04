# ML Pipeline Specification

> **Single source of truth** for the IAMS face recognition and attendance pipeline.
> Covers the full data path from camera capture to backend recognition and presence
> tracking, through to real-time streaming on the mobile app.
>
> **Migration note (2026-03):** The ML pipeline was fully replaced. FaceNet
> (InceptionResnetV1, PyTorch), MTCNN (facenet-pytorch), and MediaPipe were removed.
> The system now uses InsightFace `buffalo_l` (SCRFD 10G detector + ArcFace w600k_r50
> embedder, both ONNX Runtime) for both registration and CCTV recognition.

<!-- Last updated: 2026-03-02 -->

---

## Table of Contents

1. [Preprocessing Chain](#1-preprocessing-chain)
2. [Face Registration](#2-face-registration)
3. [Face Recognition](#3-face-recognition)
4. [Edge API Contract](#4-edge-api-contract)
5. [FAISS Lifecycle](#5-faiss-lifecycle)
6. [Streaming](#6-streaming)
7. [Threshold Reference Table](#7-threshold-reference-table)
8. [Academic References](#8-academic-references)

---

## 1. Preprocessing Chain

The preprocessing chain is now fully consolidated in the backend. The edge device
(Raspberry Pi) streams raw RTSP video; the backend samples frames and runs the
InsightFace pipeline end-to-end.

### 1.1 Edge Device (Raspberry Pi)

The edge device no longer performs face detection or cropping. Its sole
responsibility is to publish the camera stream over RTSP. The backend samples
frames directly from the RTSP URL at `RECOGNITION_FPS`.

```
Camera
  -> RTSP publish (H.264 stream)
  -> Backend samples at RECOGNITION_FPS (2.0 fps default)
```

**Key details:**

| Step | Implementation | File |
|------|---------------|------|
| Camera capture | OpenCV / PiCamera2 / RTSP | `edge/app/config.py` |
| Stream format | RTSP (H.264) | `edge/app/config.py` |
| Frame sampling | Backend samples at `RECOGNITION_FPS` | `backend/app/config.py` |

### 1.2 Backend — InsightFace Pipeline

Both the registration path (single selfies from the mobile app) and the CCTV
recognition path (sampled RTSP frames) share the same model instance and
produce numerically compatible embeddings.

```
Input image (selfie bytes or RTSP frame)
  -> InsightFaceModel._to_bgr()                 # PIL / bytes / ndarray -> BGR ndarray
  -> insightface.app.FaceAnalysis.get(bgr)       # Single call — detection + alignment + embedding
       -> SCRFD 10G (ResNet50): face detection at det_size (640x640 default)
       -> 5-point landmark detection (eyes, nose, mouth corners)
       -> Landmark-guided affine crop -> 112x112 aligned face
       -> ArcFace w600k_r50 (ResNet50): 512-dim embedding
       -> L2 normalization (normed_embedding)
  -> Output: 512-dim float32 ndarray, L2-normalized
```

**Key details:**

| Step | Implementation | File |
|------|---------------|------|
| Model wrapper | `InsightFaceModel` | `backend/app/services/ml/insightface_model.py` |
| Model pack | `buffalo_l` (ONNX, ~500 MB, downloaded on first use) | `backend/app/config.py` |
| Detector | SCRFD 10G (ResNet50 backbone) | InsightFace buffalo_l |
| Detection input size | `INSIGHTFACE_DET_SIZE = 640` (640x640) | `backend/app/config.py` |
| Alignment | 5-point landmark affine warp | InsightFace buffalo_l |
| Aligned crop size | 112x112 px (fixed by ArcFace) | InsightFace buffalo_l |
| Embedder | ArcFace w600k_r50 (ResNet50) | InsightFace buffalo_l |
| Embedding dim | 512 | `backend/app/services/ml/faiss_manager.py` |
| Normalization | L2 (`face.normed_embedding`) | InsightFace internal |
| Execution provider | CoreML on macOS (Apple Silicon); CPU elsewhere | `InsightFaceModel._get_providers()` |

**ONNX Runtime execution providers** (from `_get_providers()`):

| Platform | Providers |
|----------|-----------|
| macOS (Darwin) | `["CoreMLExecutionProvider", "CPUExecutionProvider"]` |
| Linux / Windows | `["CPUExecutionProvider"]` |

CoreML leverages the Apple Neural Engine on M-series Macs. On Linux/Windows
servers there is no CUDA provider; GPU acceleration is not used in the current
build.

---

## 2. Face Registration

Registration creates a single representative embedding from 3-5 face images
(captured at different angles on the mobile app) and stores it in both the
FAISS index and the PostgreSQL database.

### 2.1 Flow

```
Mobile app captures 3-5 face images (guided multi-angle capture)
  -> Upload as multipart files to POST /api/v1/face/register
  -> Validate: MIN_FACE_IMAGES (3) <= count <= MAX_FACE_IMAGES (5)
  -> Check user does not already have a registration (else error)
  -> For each image:
       -> Read bytes, validate file size (<= 10MB)
       -> InsightFaceModel.get_embedding(image_bytes):
            -> Convert to BGR ndarray
            -> SCRFD 10G detection -> 5-point alignment -> 112x112 crop
            -> ArcFace w600k_r50 -> 512-dim embedding
            -> L2 normalization (normed_embedding)
            -> Return 512-dim float32 ndarray
            -> On no face detected: raise ValueError (image skipped with warning)
  -> Average all valid embeddings: np.mean(embeddings, axis=0)
  -> L2 normalize the averaged embedding
  -> Add to FAISS index -> returns faiss_id
  -> Transaction safety:
       -> Insert into face_registrations table (user_id, faiss_id, embedding_bytes)
       -> On DB commit success: persist FAISS index to disk (faiss.save())
       -> On DB commit failure: rollback DB + remove FAISS entry
```

**Batch helper (`get_embeddings_batch`):** Internally calls `get_embedding()`
per image; images where SCRFD finds no face are skipped with a warning log. If
no images yield a valid face, a `ValueError` is raised and the registration is
rejected.

### 2.2 Configuration

| Parameter | Env Var | Default | Description |
|-----------|---------|---------|-------------|
| Model pack | `INSIGHTFACE_MODEL` | `buffalo_l` | InsightFace model pack name |
| Detection size | `INSIGHTFACE_DET_SIZE` | `640` | SCRFD input resolution (px, square) |
| Min images | `MIN_FACE_IMAGES` | `3` | Minimum face images for registration |
| Max images | `MAX_FACE_IMAGES` | `5` | Maximum face images for registration |
| Max upload size | `MAX_UPLOAD_SIZE_MB` | `10` | Per-image upload limit (MB) |

### 2.3 Re-registration

Users can re-register via `POST /api/v1/face/reregister`. This deletes the
old registration from the database, then runs the full registration flow
(including a new FAISS entry). The old FAISS entry is orphaned until the next
index rebuild.

---

## 3. Face Recognition

Recognition matches one or more faces from a sampled RTSP frame against all
registered embeddings using FAISS nearest-neighbor search.

### 3.1 CCTV Recognition Flow

```
RTSP frame sampled at RECOGNITION_FPS (2.0 fps default)
  -> InsightFaceModel.get_faces(frame):   # frame is BGR ndarray from cv2.VideoCapture
       -> insightface.app.FaceAnalysis.get(frame)
            -> SCRFD 10G: detect all faces in frame
            -> Per detected face:
                 -> 5-point landmark alignment -> 112x112 crop
                 -> ArcFace w600k_r50 -> 512-dim normed_embedding
       -> Return List[DetectedFace] (empty list if no faces or model not loaded)
  -> For each DetectedFace:
       -> FAISS search_with_margin(embedding):
            -> Search top-K (RECOGNITION_TOP_K=3) neighbors with threshold=0.0
            -> If top-1 cosine similarity < RECOGNITION_THRESHOLD (0.45): no match
            -> If top-1 >= 0.45:
                 -> Compute gap = top-1 score - top-2 score
                 -> If gap <= RECOGNITION_MARGIN (0.1): flag as ambiguous
                 -> Attach user_id + similarity to DetectedFace
  -> Push DetectedFace list via WebSocket
  -> Feed matched user_ids to PresenceService
```

**Note on threshold:** `RECOGNITION_THRESHOLD = 0.45` (lower than the former
0.55) was calibrated for cross-camera matching where embeddings from a wide-angle
CCTV frame may differ slightly from registration selfies.

### 3.2 Single Registration Embedding Flow

Used only during face registration (not CCTV recognition).

```
Input: single image bytes from mobile upload
  -> InsightFaceModel.get_embedding(image):
       -> SCRFD 10G detection (largest face selected)
       -> 5-point alignment -> 112x112 crop
       -> ArcFace w600k_r50 -> 512-dim normed_embedding
  -> Return 512-dim float32 ndarray
```

### 3.3 Configuration

| Parameter | Env Var | Default | Description |
|-----------|---------|---------|-------------|
| Recognition threshold | `RECOGNITION_THRESHOLD` | `0.45` | Cosine similarity threshold for a match |
| Recognition margin | `RECOGNITION_MARGIN` | `0.1` | Min gap between top-1 and top-2 to be non-ambiguous |
| Top-K neighbors | `RECOGNITION_TOP_K` | `3` | FAISS neighbors to retrieve per query |
| Detection size | `INSIGHTFACE_DET_SIZE` | `640` | SCRFD input resolution (px, square) |
| Recognition FPS | `RECOGNITION_FPS` | `2.0` | Frames per second sampled for recognition |
| Max batch size | `RECOGNITION_MAX_BATCH_SIZE` | `50` | Max faces per backend batch pass |

---

## 4. Edge API Contract

### 4.1 Endpoint

```
POST /api/v1/face/process
Content-Type: application/json
```

No authentication required (trusted network). In production, use an API key or
service account token.

### 4.2 Request Schema

```json
{
  "request_id": "optional-idempotency-key",
  "room_id": "uuid-or-alphanumeric-id",
  "timestamp": "2024-01-15T10:30:00Z",
  "faces": [
    {
      "image": "<base64-encoded-jpeg>",
      "bbox": [100, 150, 112, 112]
    }
  ]
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `request_id` | `string` | No | Max 100 chars. Idempotency key (5-min TTL). |
| `room_id` | `string` | Yes | Max 100 chars. Pattern: `^[a-zA-Z0-9\-]+$` |
| `timestamp` | `datetime` | Yes | ISO 8601 format |
| `faces` | `array[FaceData]` | Yes | **Min 1, max 10** items per request |
| `faces[].image` | `string` | Yes | Base64-encoded JPEG. Max 15MB encoded. |
| `faces[].bbox` | `array[int]` | No | `[x, y, width, height]`. All >= 0, w/h > 0. |

**Optimal batch size:** 3-5 faces per request (balances throughput and latency).

### 4.3 Response Schema

```json
{
  "success": true,
  "data": {
    "processed": 5,
    "matched": [
      { "user_id": "uuid-1", "confidence": 0.72 },
      { "user_id": "uuid-2", "confidence": 0.81 }
    ],
    "unmatched": 3,
    "processing_time_ms": 245,
    "presence_logged": 2
  }
}
```

### 4.4 Error Handling

**HTTP 422** is returned for validation errors (malformed request body,
`faces` array empty or exceeding 10 items, invalid `room_id` pattern, etc.).

Per-face errors are tracked internally and logged but do not fail the overall
request. The response `success` field is `true` as long as the request was
structurally valid.

| Error Code | Retry? | Description |
|------------|--------|-------------|
| `INVALID_IMAGE_FORMAT` | No | Bad Base64, unsupported format, image too small/large |
| `RECOGNITION_FAILED` | Yes | Transient model/inference error |
| `PROCESSING_FAILED` | Yes | Unexpected error during face processing |
| `DATABASE_UNAVAILABLE` | Yes (backoff) | DB connection failure during presence logging |

### 4.5 Idempotency

When `request_id` is provided, the backend deduplicates requests using an
in-memory cache with a **5-minute TTL**. Duplicate requests within the TTL
window return immediately with `processed=0`.

Cache key format: `{request_id}:{room_id}:{timestamp_iso}`

### 4.6 Presence Logging

After recognition, matched users are fed to the presence tracking system:

1. Look up the current schedule for the given `room_id`, day-of-week, and time.
2. For each matched user, call `PresenceService.feed_detection()` which updates
   the DeepSORT tracking service.
3. Presence scans run every 60 seconds (`SCAN_INTERVAL_SECONDS`) via a background
   scheduler. Three consecutive missed scans (`EARLY_LEAVE_THRESHOLD=3`) trigger
   an early-leave alert.

---

## 5. FAISS Lifecycle

### 5.1 Index Type

**`faiss.IndexFlatIP`** -- exact inner-product search on L2-normalized vectors,
which is equivalent to cosine similarity. Dimension: **512**.

This is unchanged from the prior pipeline. InsightFace ArcFace embeddings are
also 512-dimensional and L2-normalized, so the FAISS index is fully compatible.

### 5.2 No Native Delete

`IndexFlatIP` does not support native vector deletion. The workaround:

- **Soft delete:** Remove the `faiss_id -> user_id` mapping from the in-memory
  `user_map` dict. The vector remains in the index but is never returned in
  search results.
- **Hard delete (rebuild):** Call `FAISSManager.rebuild(embeddings_data)` which
  creates a fresh index from all active registrations in the database.

Rebuild is triggered by:
- `FaceService.deregister_face()` (user removal)
- `FaceService.reconcile_faiss_index()` (startup reconciliation)

### 5.3 Startup Reconciliation

On application startup, `FaceService.reconcile_faiss_index()` compares the
FAISS vector count (`index.ntotal`) against the count of active records in the
`face_registrations` table. If they differ, the index is rebuilt from the
database to recover from crashes or interrupted operations.

After loading/rebuilding, user mappings are populated from the database:

```python
for reg in active_registrations:
    faiss_manager.user_map[reg.embedding_id] = str(reg.user_id)
```

### 5.4 Disk Persistence

- FAISS index is persisted to `FAISS_INDEX_PATH` (default: `data/faiss/faces.index`).
- **Save after every add:** `faiss.save()` is called after each successful
  registration (after DB commit succeeds).
- **Save on rebuild:** `faiss.save()` is called at the end of `rebuild()`.
- **Save on shutdown:** `FaceService.save_faiss_index()` is called during
  application shutdown.

### 5.5 Health Check

The FAISS manager exposes `get_stats()`:

```json
{
  "initialized": true,
  "total_vectors": 42,
  "dimension": 512,
  "index_type": "IndexFlatIP",
  "user_mappings": 42
}
```

A mismatch between `total_vectors` and `user_mappings` indicates orphaned
vectors (from soft deletes) and suggests a rebuild is needed.

---

## 6. Streaming

IAMS supports two streaming modes controlled by `USE_HLS_STREAMING` (default: `True`).

### 6.1 HLS Mode (Default)

**Video delivery:** FFmpeg remuxes the RTSP stream to HLS format.

```
RTSP source (camera)
  -> FFmpeg (codec copy, no transcode)
     -r 30                          # Output at 30fps
     -c:v copy                      # Remux, near-zero CPU
     -an                            # No audio
     -f hls
     -hls_time 2                    # 2-second segments (HLS_SEGMENT_DURATION)
     -hls_list_size 3               # 3-segment sliding window (HLS_PLAYLIST_SIZE)
     -hls_flags delete_segments+append_list
  -> .m3u8 playlist + .ts segments in data/hls/{room_id}/
  -> Served via GET /api/v1/hls/{room_id}/playlist.m3u8
```

**One FFmpeg process per room**, shared across all viewers (reference counted).
When the last viewer disconnects, the process is killed and segments are
cleaned up.

**Detection metadata:** A separate recognition pipeline reads the RTSP stream
at `RECOGNITION_FPS` (2.0 fps) on a background thread. Results are pushed to
connected clients via WebSocket at ~8 Hz (`poll_interval = 0.125s`).

**WebSocket message format (HLS mode):**

```json
{
  "type": "detections",
  "timestamp": "2024-01-15T10:30:00.125Z",
  "detections": [
    {
      "bbox": { "x": 100, "y": 150, "width": 80, "height": 80 },
      "confidence": 0.95,
      "user_id": "uuid-1",
      "name": "Juan Dela Cruz",
      "student_id": "2021-0001",
      "similarity": 0.72
    }
  ],
  "detection_width": 1280,
  "detection_height": 720
}
```

Other message types: `connected` (with `hls_url`), `heartbeat` (every 5s),
`pong` (response to client `ping`).

### 6.2 Legacy Mode

When `USE_HLS_STREAMING=false`, JPEG frames are base64-encoded and sent over
WebSocket as `type: "frame"` messages (~50-100KB per frame at `STREAM_FPS`).

### 6.3 Mobile Overlay

The React Native `DetectionOverlay` component renders bounding boxes on top of
the HLS video player:

- Scales detection coordinates from backend resolution (`detection_width` x
  `detection_height`) to on-screen container dimensions, accounting for
  letterboxing (`contain` mode).
- Each detection box uses an `Animated.timing` fade-in with
  **`FADE_DURATION = 200ms`**.
- Recognized faces: green border (`#00C853`). Unknown faces: yellow border
  (`#FFD600`).
- Labels show student name (or ID) and similarity percentage.

### 6.4 Configuration

| Parameter | Env Var | Default | Description |
|-----------|---------|---------|-------------|
| HLS enabled | `USE_HLS_STREAMING` | `True` | Feature flag for HLS mode |
| Segment duration | `HLS_SEGMENT_DURATION` | `2` | Seconds per `.ts` segment |
| Playlist size | `HLS_PLAYLIST_SIZE` | `3` | Sliding-window segment count |
| Segment directory | `HLS_SEGMENT_DIR` | `data/hls` | Storage for `.m3u8` / `.ts` files |
| FFmpeg path | `HLS_FFMPEG_PATH` | `bin/ffmpeg.exe` | Path to FFmpeg binary |
| Recognition FPS | `RECOGNITION_FPS` | `2.0` | Frames/sec sampled for recognition |
| Max batch size | `RECOGNITION_MAX_BATCH_SIZE` | `50` | Max faces per batch forward pass |
| Recognition RTSP | `RECOGNITION_RTSP_URL` | `""` | Separate high-res RTSP for recognition |
| Recognition max dim | `RECOGNITION_MAX_DIM` | `1280` | Cap frame dimension for detection |
| Legacy stream FPS | `STREAM_FPS` | `3` | FPS for legacy JPEG-over-WS mode |
| Legacy JPEG quality | `STREAM_QUALITY` | `65` | JPEG quality for legacy mode |
| Stream width | `STREAM_WIDTH` | `1280` | Output width (pixels) |
| Stream height | `STREAM_HEIGHT` | `720` | Output height (pixels) |

---

## 7. Threshold Reference Table

All configurable thresholds with their environment variable names, defaults,
and valid ranges. All are set in backend or edge `.env` files.

### 7.1 Edge Device Thresholds

| Parameter | Env Var | Default | Valid Range | Description |
|-----------|---------|---------|-------------|-------------|
| Scan interval | `SCAN_INTERVAL` | `60` | > 0 | Seconds between edge scans |
| Queue max size | `QUEUE_MAX_SIZE` | `500` | > 0 | Offline queue capacity |
| Queue TTL | `QUEUE_TTL_SECONDS` | `300` | > 0 | Queue item expiry (seconds) |
| Retry interval | `RETRY_INTERVAL_SECONDS` | `10` | > 0 | Seconds between retries |
| Retry max attempts | `RETRY_MAX_ATTEMPTS` | `3` | > 0 | Max retry attempts per item |

### 7.2 Backend Recognition Thresholds

| Parameter | Env Var | Default | Valid Range | Description |
|-----------|---------|---------|-------------|-------------|
| InsightFace model | `INSIGHTFACE_MODEL` | `buffalo_l` | string | InsightFace model pack name |
| Detection size | `INSIGHTFACE_DET_SIZE` | `640` | > 0 | SCRFD input resolution (px, square) |
| Recognition threshold | `RECOGNITION_THRESHOLD` | `0.45` | 0.0 - 1.0 | ArcFace cosine similarity threshold |
| Recognition margin | `RECOGNITION_MARGIN` | `0.1` | 0.0 - 1.0 | Min gap between top-1 and top-2 scores |
| Top-K neighbors | `RECOGNITION_TOP_K` | `3` | >= 1 | FAISS neighbors to retrieve |
| Min face images | `MIN_FACE_IMAGES` | `3` | >= 1 | Min images for registration |
| Max face images | `MAX_FACE_IMAGES` | `5` | >= MIN_FACE_IMAGES | Max images for registration |
| FAISS index path | `FAISS_INDEX_PATH` | `data/faiss/faces.index` | valid path | Disk path for FAISS index |

### 7.3 Presence Tracking Thresholds

| Parameter | Env Var | Default | Valid Range | Description |
|-----------|---------|---------|-------------|-------------|
| Scan interval | `SCAN_INTERVAL_SECONDS` | `60` | > 0 | Seconds between presence scans |
| Early leave threshold | `EARLY_LEAVE_THRESHOLD` | `3` | >= 1 | Consecutive misses to flag early leave |
| Grace period | `GRACE_PERIOD_MINUTES` | `15` | >= 0 | Late grace period after class start |
| Session buffer | `SESSION_BUFFER_MINUTES` | `5` | >= 0 | Buffer before/after class for session |

### 7.4 Streaming Thresholds

| Parameter | Env Var | Default | Valid Range | Description |
|-----------|---------|---------|-------------|-------------|
| HLS enabled | `USE_HLS_STREAMING` | `True` | True/False | HLS mode feature flag |
| HLS segment duration | `HLS_SEGMENT_DURATION` | `2` | >= 1 | Seconds per `.ts` segment |
| HLS playlist size | `HLS_PLAYLIST_SIZE` | `3` | >= 1 | Sliding-window segment count |
| Recognition FPS | `RECOGNITION_FPS` | `2.0` | > 0 | Detection sampling rate |
| Recognition max batch | `RECOGNITION_MAX_BATCH_SIZE` | `50` | >= 1 | Max faces per forward pass |
| Recognition max dim | `RECOGNITION_MAX_DIM` | `1280` | > 0 | Cap frame dimension for detection |
| WS poll interval | (hardcoded) | `0.125` | > 0 | WebSocket push interval (seconds) = 8 Hz |
| WS heartbeat interval | (hardcoded) | `5.0` | > 0 | Heartbeat interval (seconds) |
| Overlay fade duration | (hardcoded) | `200` | >= 0 | Mobile overlay fade-in (ms) |
| Legacy stream FPS | `STREAM_FPS` | `3` | > 0 | JPEG-over-WS frame rate |
| Legacy JPEG quality | `STREAM_QUALITY` | `65` | 1 - 100 | Legacy mode JPEG quality |

### 7.5 Edge API Thresholds

| Parameter | Env Var | Default | Valid Range | Description |
|-----------|---------|---------|-------------|-------------|
| Max faces per request | (hardcoded in schema) | `10` | 1 - 10 | Max `faces` array length |
| Min faces per request | (hardcoded in schema) | `1` | >= 1 | Min `faces` array length |
| Idempotency TTL | (hardcoded) | `300` | > 0 | Request dedup cache TTL (seconds) |
| Max Base64 size | (hardcoded) | `15,000,000` | > 0 | Max encoded image size (bytes) |
| Max decoded size | (hardcoded) | `10,000,000` | > 0 | Max decoded image size (bytes) |
| Max image dimension | (hardcoded) | `4096` | > 0 | Max image width/height (px) |
| Rate limit (recommended) | -- | `1/sec/room` | -- | Recommended max request rate |

---

## 8. Academic References

This section documents the foundational work underlying the IAMS ML pipeline,
for inclusion in the project thesis.

**ArcFace (face recognition):**

> Deng, J., Guo, J., Xue, N., & Zafeiriou, S. (2019). ArcFace: Additive Angular
> Margin Loss for Deep Face Recognition. In *Proceedings of the IEEE/CVF Conference
> on Computer Vision and Pattern Recognition (CVPR)*, pp. 4690-4699.

ArcFace introduces an additive angular margin loss (CosFace variant) to improve
discriminative power of face embeddings. The w600k_r50 model (ResNet50 backbone,
trained on WebFace600K) used in IAMS produces 512-dimensional embeddings and is
distributed as part of the InsightFace `buffalo_l` model pack.

**SCRFD (face detection):**

> Guo, J., Deng, J., Lattas, A., & Zafeiriou, S. (2021). Sample and Computation
> Redistribution for Efficient Face Detection. In *Proceedings of the IEEE/CVF
> International Conference on Computer Vision (ICCV)*, pp. 1468-1477.

SCRFD (Sample and Computation Redistribution for Face Detection) uses a ResNet50
backbone with a feature pyramid network and redistributes computation across
scales for improved accuracy-efficiency trade-offs. The SCRFD-10GF model used
in IAMS (part of `buffalo_l`) is calibrated for high-resolution frames.

**InsightFace library:**

> Deng, J., Guo, J., Feng, Z., Liu, C., & Zafeiriou, S. (2022). InsightFace:
> An Open Source 2D&3D Deep Face Analysis Library. *arXiv preprint*
> arXiv:2112.05905.

InsightFace provides the unified `FaceAnalysis.get()` API used by IAMS to run
SCRFD detection, 5-point landmark alignment, and ArcFace embedding in a single
call. The `buffalo_l` model pack bundles SCRFD-10GF and w600k_r50 as ONNX
models, removing the PyTorch runtime dependency entirely.
