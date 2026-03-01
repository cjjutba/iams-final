# ML Pipeline Specification

> **Single source of truth** for the IAMS face recognition and attendance pipeline.
> Covers the full data path from camera capture on the Raspberry Pi edge device,
> through backend recognition and presence tracking, to real-time streaming on
> the mobile app.

---

## Table of Contents

1. [Preprocessing Chain](#1-preprocessing-chain)
2. [Face Registration](#2-face-registration)
3. [Face Recognition](#3-face-recognition)
4. [Edge API Contract](#4-edge-api-contract)
5. [FAISS Lifecycle](#5-faiss-lifecycle)
6. [Streaming](#6-streaming)
7. [Threshold Reference Table](#7-threshold-reference-table)

---

## 1. Preprocessing Chain

The preprocessing chain spans two tiers: the edge device (Raspberry Pi) handles
detection and cropping; the backend handles alignment, embedding, and search.

### 1.1 Edge Device (Raspberry Pi)

```
Camera capture (BGR, 640x480 @ 15fps default)
  -> MediaPipe Face Detection (short-range model, confidence >= 0.6)
     -> Discard detections smaller than 80x80 px (MIN_FACE_PIXELS)
     -> Downscale frame to max 1280px before detection if needed
  -> Crop face region with 20% padding on each side
     -> Clamp to frame boundaries
  -> Resize crop to 160x160 px (FACE_CROP_SIZE)
  -> JPEG encode at 85% quality (JPEG_QUALITY)
  -> Base64 encode
  -> POST to backend /api/v1/face/process
```

**Key details:**

| Step | Implementation | File |
|------|---------------|------|
| Camera capture | OpenCV / PiCamera2 / RTSP | `edge/app/config.py` |
| Face detection | MediaPipe Tasks API, `blaze_face_short_range.tflite` | `edge/app/detector.py` |
| Min detection confidence | `DETECTION_CONFIDENCE = 0.6` | `edge/app/config.py` |
| Min face size | `MIN_FACE_PIXELS = 80` (width and height) | `edge/app/detector.py` |
| Max detection dimension | `MAX_DETECT_DIM = 1280` | `edge/app/detector.py` |
| Crop padding | 20% (`padding=0.2`) | `edge/app/processor.py` |
| Crop resize | `FACE_CROP_SIZE = 160` (160x160 px) | `edge/app/config.py` |
| JPEG quality | `JPEG_QUALITY = 85` | `edge/app/config.py` |
| Encoding | `base64.b64encode(jpeg_bytes)` | `edge/app/processor.py` |

### 1.2 Backend

```
Receive Base64 string
  -> Decode Base64 (reject if > 15MB encoded / 10MB decoded)
  -> Validate image format (JPEG or PNG only)
  -> Validate dimensions >= 160x160, <= 4096x4096
  -> If USE_FACE_ALIGNMENT is True:
       -> MTCNN alignment (detect landmarks, align face)
       -> Fallback: use raw crop if MTCNN finds no landmarks
  -> Resize to 160x160 (FACE_IMAGE_SIZE) using PIL BILINEAR
  -> Normalize pixel values to [-1, 1]:  (pixel - 127.5) / 128.0
  -> Convert to tensor [1, 3, 160, 160] (CHW format)
  -> FaceNet forward pass (InceptionResnetV1, VGGFace2 pretrained)
  -> Output: 512-dimensional embedding
  -> L2 normalize embedding
```

**Key details:**

| Step | Implementation | File |
|------|---------------|------|
| Base64 decode + validation | `FaceNetModel.decode_base64_image()` | `backend/app/services/ml/face_recognition.py` |
| MTCNN alignment | `FaceNetModel.align_face()` via `facenet_pytorch.MTCNN` | `backend/app/services/ml/face_recognition.py` |
| MTCNN config | `image_size=160, margin=0, min_face_size=20, select_largest=True, post_process=False` | `backend/app/services/ml/face_recognition.py` |
| Preprocessing | `FaceNetModel.preprocess_image()` | `backend/app/services/ml/face_recognition.py` |
| Normalization formula | `(pixel - 127.5) / 128.0` | `backend/app/services/ml/face_recognition.py` |
| Model | `InceptionResnetV1(pretrained='vggface2')` | `backend/app/services/ml/face_recognition.py` |
| Embedding dim | 512 | `backend/app/services/ml/faiss_manager.py` |
| L2 normalization | `embedding / np.linalg.norm(embedding)` | `backend/app/services/ml/face_recognition.py` |

---

## 2. Face Registration

Registration creates a single representative embedding from 3-5 face images
(captured at different angles on the mobile app) and stores it in both the
FAISS index and the PostgreSQL database.

### 2.1 Flow

```
Mobile app captures 3-5 face images (guided 5-angle capture)
  -> Upload as multipart files to POST /api/v1/face/register
  -> Validate: MIN_FACE_IMAGES (3) <= count <= MAX_FACE_IMAGES (5)
  -> Check user does not already have a registration (else error)
  -> For each image:
       -> Read bytes, validate file size (<= 10MB)
       -> generate_embedding(image_bytes):
            -> MTCNN alignment (if USE_FACE_ALIGNMENT=True)
            -> Preprocess: resize 160x160, normalize [-1,1]
            -> FaceNet forward pass -> 512-dim embedding
            -> L2 normalize
  -> Average all embeddings: np.mean(embeddings, axis=0)
  -> L2 normalize the averaged embedding
  -> Add to FAISS index -> returns faiss_id
  -> Transaction safety:
       -> Insert into face_registrations table (user_id, faiss_id, embedding_bytes)
       -> On DB commit success: persist FAISS index to disk (faiss.save())
       -> On DB commit failure: rollback DB + remove FAISS entry
```

### 2.2 Configuration

| Parameter | Env Var | Default | Description |
|-----------|---------|---------|-------------|
| Min images | `MIN_FACE_IMAGES` | `3` | Minimum face images for registration |
| Max images | `MAX_FACE_IMAGES` | `5` | Maximum face images for registration |
| Max upload size | `MAX_UPLOAD_SIZE_MB` | `10` | Per-image upload limit (MB) |
| Face alignment | `USE_FACE_ALIGNMENT` | `True` | Enable MTCNN alignment before embedding |

### 2.3 Re-registration

Users can re-register via `POST /api/v1/face/reregister`. This deletes the
old registration from the database, then runs the full registration flow
(including a new FAISS entry). The old FAISS entry is orphaned until the next
index rebuild.

---

## 3. Face Recognition

Recognition matches an incoming face crop against all registered embeddings
using FAISS nearest-neighbor search with a confidence margin check.

### 3.1 Single Recognition Flow

```
Input: image bytes (from edge device or test endpoint)
  -> generate_embedding(image_bytes)
       -> MTCNN alignment (if enabled) -> preprocess -> FaceNet -> L2 normalize
  -> FAISS search_with_margin(embedding):
       -> Search top-K (RECOGNITION_TOP_K=3) neighbors with threshold=0.0
       -> If top-1 score < RECOGNITION_THRESHOLD (0.55): no match
       -> If top-1 score >= 0.55:
            -> Compute gap = top-1 score - top-2 score
            -> If gap <= RECOGNITION_MARGIN (0.1): flag as ambiguous
            -> Return user_id, confidence, is_ambiguous
  -> Ambiguous matches: logged with warning but still accepted (user_id returned)
```

### 3.2 Batch Recognition Flow

Used by the Edge API and the recognition service for processing multiple
faces in a single request.

```
Input: list of image bytes
  -> Phase 1: Decode all images (Base64 or raw bytes -> PIL)
  -> Phase 2: Batch embedding via generate_embeddings_batch()
       -> Preprocess each image -> stack tensors -> single forward pass [N,3,160,160] -> [N,512]
       -> L2 normalize each row
  -> Phase 3: Batch FAISS search via search_batch(embeddings, k=RECOGNITION_TOP_K)
       -> For each query, return matches above RECOGNITION_THRESHOLD
```

### 3.3 Configuration

| Parameter | Env Var | Default | Description |
|-----------|---------|---------|-------------|
| Threshold | `RECOGNITION_THRESHOLD` | `0.55` | Cosine similarity threshold for a match |
| Margin | `RECOGNITION_MARGIN` | `0.1` | Min gap between top-1 and top-2 to be non-ambiguous |
| Top-K | `RECOGNITION_TOP_K` | `3` | Number of neighbors to retrieve from FAISS |
| GPU | `USE_GPU` | `True` | Use CUDA if available, fallback to CPU |
| Face alignment | `USE_FACE_ALIGNMENT` | `True` | MTCNN alignment before embedding |

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
      { "user_id": "uuid-1", "confidence": 0.85 },
      { "user_id": "uuid-2", "confidence": 0.92 }
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
at `RECOGNITION_FPS` (8 fps) on a background thread. Results are pushed to
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
      "similarity": 0.87
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
| Recognition FPS | `RECOGNITION_FPS` | `8.0` | Frames/sec sampled for recognition |
| Max batch size | `RECOGNITION_MAX_BATCH_SIZE` | `20` | Max faces per batch forward pass |
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
| Detection confidence | `DETECTION_CONFIDENCE` | `0.6` | 0.0 - 1.0 | MediaPipe min detection confidence |
| Detection model | `DETECTION_MODEL` | `0` | 0 or 1 | 0 = short-range (only supported model) |
| Min face pixels | (hardcoded) | `80` | > 0 | Min bbox dimension in px to accept |
| Max detect dimension | (hardcoded) | `1280` | > 0 | Downscale frame if larger |
| Face crop size | `FACE_CROP_SIZE` | `160` | > 0 | Resize crop before JPEG encode (px) |
| JPEG quality | `JPEG_QUALITY` | `85` | 1 - 100 | JPEG compression quality |
| Crop padding | (hardcoded) | `0.2` | 0.0 - 1.0 | Padding ratio around face bbox |
| Scan interval | `SCAN_INTERVAL` | `60` | > 0 | Seconds between edge scans |
| Queue max size | `QUEUE_MAX_SIZE` | `500` | > 0 | Offline queue capacity |
| Queue TTL | `QUEUE_TTL_SECONDS` | `300` | > 0 | Queue item expiry (seconds) |
| Retry interval | `RETRY_INTERVAL_SECONDS` | `10` | > 0 | Seconds between retries |
| Retry max attempts | `RETRY_MAX_ATTEMPTS` | `3` | > 0 | Max retry attempts per item |

### 7.2 Backend Recognition Thresholds

| Parameter | Env Var | Default | Valid Range | Description |
|-----------|---------|---------|-------------|-------------|
| Recognition threshold | `RECOGNITION_THRESHOLD` | `0.55` | 0.0 - 1.0 | Cosine similarity threshold for a match |
| Recognition margin | `RECOGNITION_MARGIN` | `0.1` | 0.0 - 1.0 | Min gap between top-1 and top-2 scores |
| Top-K neighbors | `RECOGNITION_TOP_K` | `3` | >= 1 | FAISS neighbors to retrieve |
| Face alignment | `USE_FACE_ALIGNMENT` | `True` | True/False | Enable MTCNN alignment |
| GPU usage | `USE_GPU` | `True` | True/False | Use CUDA if available |
| Face image size | `FACE_IMAGE_SIZE` | `160` | > 0 | FaceNet input dimensions (px) |
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
| Recognition FPS | `RECOGNITION_FPS` | `8.0` | > 0 | Detection sampling rate |
| Recognition max batch | `RECOGNITION_MAX_BATCH_SIZE` | `20` | >= 1 | Max faces per forward pass |
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
