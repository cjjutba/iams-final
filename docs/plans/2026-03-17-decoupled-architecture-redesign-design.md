# Decoupled Architecture Redesign — Design Document

**Date:** 2026-03-17
**Status:** Approved
**Branch:** `feat/architecture-redesign`

## Problem Statement

The current IAMS architecture couples attendance recording with live video processing in a single pipeline. When the video pipeline crashes (FFmpeg decode hiccup, ByteTrack edge case, encoder deadlock), attendance recording also fails. A student can be marked absent because of a video encoding bug. This is unacceptable for a system whose primary purpose is reliable attendance tracking.

Additionally, the current pipeline has numerous stability issues:
- RTSPReader hangs indefinitely on FFmpeg exit
- FFmpegPublisher pipe buffer can deadlock the entire pipeline
- FAISS deletion only clears user_map, not the index (orphaned vectors)
- Race conditions in presence service (concurrent scans lose detections)
- Single-worker limitation prevents scaling
- Synchronous DB calls block the async event loop
- Production docker-compose references non-existent worker modules

## Core Insight

**Attendance tracking and live video are fundamentally different workloads with different reliability requirements.** They must be decoupled.

| Concern | Attendance Engine | Live Feed Pipeline |
|---------|-------------------|-------------------|
| Purpose | Record who's present, detect early leave | Show annotated video to faculty |
| Failure tolerance | Near-zero — affects grades | High — cosmetic feature |
| Processing model | 1 frame every 15 seconds | 20 frames per second continuous |
| CPU cost | ~1% of a core | ~80-100% of a core |
| Complexity | Trivial (grab, detect, recognize, write) | High (decode, track, annotate, encode) |
| Must run | Always, during active sessions | Only while session is active |

## Architecture

```
CAMERA LAYER
  Reolink P340 (RTSP H.264)
       |
       v
  RPi FFmpeg relay (dumb, no ML)
       |
       v
  mediamtx on VPS (single RTSP ingest: /room/{id}/raw)
       |
       +---> Attendance Engine (reads 1 frame every 15s)
       |
       +---> Live Feed Pipeline (reads at 20fps, session-bound)


ATTENDANCE ENGINE (System 1 — the brain)
  APScheduler job per active session, every 15s:
    1. FrameGrabber.grab() -> latest frame (instant, from persistent connection)
    2. SCRFD detect all faces
    3. ArcFace recognize each face via FAISS
    4. Compare with previous scan -> update miss counters
    5. Write to DB (attendance_records, presence_logs)
    6. Write identities to Redis shared cache
    7. WebSocket notify mobile (present list, early-leave alerts)


LIVE FEED PIPELINE (System 2 — the eyes)
  Subprocess per room, session-bound lifecycle:
    1. RTSPReader decodes /room/{id}/raw at 20fps
    2. Every 3rd frame: SCRFD detection
       Other frames: ByteTrack Kalman prediction
    3. New tracks -> check Redis cache for identity
       Cache miss -> lazy-load ArcFace, run recognition (fallback)
    4. FrameAnnotator draws boxes + names onto frame
    5. FFmpegPublisher encodes H.264 -> /room/{id}/live
    6. mediamtx serves via WebRTC (WHEP) to mobile


ONE-WAY REDIS CACHE BRIDGE
  Attendance Engine WRITES:
    attendance:{room_id}:{session_id}:identities
      -> Hash: { user_id: JSON{name, confidence, bbox, last_seen_ts} }
    attendance:{room_id}:{session_id}:scan_meta
      -> Hash: { last_scan_ts, faces_detected, faces_recognized }

  Live Feed Pipeline READS:
    -> Uses cached identities to label tracked faces
    -> Only runs ArcFace on cache miss (new face mid-class)
    -> No write access to attendance keys


MOBILE APP
  Faculty:
    - WebRTC player showing /room/{id}/live (annotated stream)
    - Attendance dashboard (present/absent/late via WebSocket)
    - Early-leave alert notifications
  Student:
    - Face registration (camera capture -> upload)
    - Attendance status and history
```

## Key Components

### FrameGrabber (Attendance Engine)

Persistent RTSP connection that continuously drains frames, keeping only the latest. The attendance engine calls `grab()` every 15 seconds — instant return, no connection overhead.

```python
class FrameGrabber:
    def __init__(self, rtsp_url: str):
        self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        self._latest_frame = None
        self._last_update = 0.0
        self._lock = threading.Lock()
        self._thread = Thread(target=self._drain_loop, daemon=True)
        self._thread.start()

    def _drain_loop(self):
        while True:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame
                    self._last_update = time.time()
            else:
                time.sleep(0.1)  # avoid busy-spin on connection loss

    def grab(self) -> np.ndarray | None:
        with self._lock:
            if self._latest_frame is None:
                return None
            if time.time() - self._last_update > 30:  # stale for 30s
                self._reconnect()
                return None
            return self._latest_frame.copy()

    def _reconnect(self):
        self.cap.release()
        self.cap = cv2.VideoCapture(self._rtsp_url, cv2.CAP_FFMPEG)
        self._latest_frame = None
```

Thread safety: Lock around `_latest_frame` because `.copy()` on a partially-written numpy array is not guaranteed safe despite the GIL.

Staleness check: If no new frame for 30 seconds, reconnects and returns None. The attendance engine skips that scan and retries next interval.

### Attendance Scan Cycle

```
Every 15 seconds per active session:
  frame = frame_grabber.grab()
  if frame is None:
      log.warning("No frame available, skipping scan")
      return

  faces = scrfd.detect(frame)  # returns list of (bbox, confidence)

  for bbox, conf in faces:
      crop = frame[y1:y2, x1:x2]
      embedding = arcface.get_embedding(crop)
      match = faiss_index.search(embedding, k=1)

      if match.confidence >= threshold:
          mark_present(match.user_id, session_id)
          reset_miss_counter(match.user_id)
          write_to_redis_cache(match.user_id, match.name, bbox)
      else:
          log_unknown_face(bbox)

  # Check for absences
  for enrolled_student in session.enrolled:
      if not detected_this_scan(enrolled_student):
          increment_miss_counter(enrolled_student)
          if miss_counter >= 3:
              flag_early_leave(enrolled_student)
              notify_faculty(enrolled_student)

  update_scan_meta_redis(session_id, len(faces), len(matches))
```

### Live Feed Pipeline

Same core as current `video_pipeline.py` but:
- **No attendance logic.** Does not write to DB. Does not track miss counters.
- **Reads Redis cache** for face identities instead of running ArcFace on every new track.
- **ArcFace loaded lazily** — only on first cache miss.
- **Session-bound lifecycle** — starts when session starts, stops when session ends.

### Redis Key Design

```
# Identity cache (written by attendance engine, read by pipeline)
attendance:{room_id}:{session_id}:identities
  -> Redis Hash
  -> Key: user_id (string)
  -> Value: JSON { "name": "Juan Dela Cruz", "confidence": 0.95,
                   "bbox": [x1,y1,x2,y2], "last_seen_ts": 1710680400 }
  -> TTL: session duration + 5 minutes (auto-cleanup)

# Scan metadata (written by attendance engine, read by mobile/monitoring)
attendance:{room_id}:{session_id}:scan_meta
  -> Redis Hash
  -> Keys: last_scan_ts, faces_detected, faces_recognized, scan_count
  -> TTL: session duration + 5 minutes

# Pipeline state (written by pipeline, read by mobile for status)
pipeline:{room_id}:status
  -> Redis Hash
  -> Keys: state (running/stopped/error), fps, tracks_count, uptime_s
  -> TTL: 60 seconds (auto-expires if pipeline dies)
```

## Failure Modes

| Failure | Attendance Impact | Live Feed Impact | Recovery |
|---------|-------------------|-------------------|----------|
| RPi internet drops | Stops (no source) | Stops (no source) | Auto-resumes when RPi reconnects |
| mediamtx crashes | FrameGrabber returns None, skips scan | Pipeline dies | Docker auto-restart, both reconnect |
| Attendance engine exception | Skips one scan, retries next interval | None | APScheduler catches exception, logs, continues |
| Live feed pipeline crash | None | Faculty sees "feed unavailable" | PipelineManager auto-restarts subprocess |
| Redis crash | Writes to DB directly (core job) | Falls back to own ArcFace | Docker auto-restart |
| ArcFace returns no match | Student logged as "detected, unrecognized" | Shows "Unknown" label | Expected for unregistered faces |
| DB connection failure | Buffers in memory, retries next scan | None | Connection pool retry |

**Key guarantee:** No single component failure causes both attendance AND live feed to fail (except camera source loss, which is unrecoverable by design).

## Known Limitations

1. **No internet = no attendance.** The RPi is a dumb relay. If campus WiFi drops, neither system has a source. Accepted for thesis — campus WiFi is stable and this is documented as a known limitation.

2. **Double model loading.** SCRFD is loaded in both attendance engine and pipeline (~60MB total). ArcFace is loaded in attendance engine (~250MB) and lazily in pipeline (only on cache miss). Total ~340MB best case, ~590MB worst case.

3. **Single room pilot.** Architecture supports multiple rooms but has only been tested with one camera. Multi-room deployment is a future extension.

## Deployment

### Docker Compose (Production)

```yaml
services:
  api-gateway:     # FastAPI + attendance engine + pipeline manager
  redis:           # Shared cache + pipeline state
  mediamtx:        # RTSP ingest + WebRTC serving
  nginx:           # Reverse proxy + TLS
```

The live feed pipeline runs as a subprocess spawned by the api-gateway container. The api-gateway Dockerfile must include FFmpeg and sufficient memory limits for both the API server and video processing.

### Container Requirements

| Container | CPU | Memory | Ports |
|-----------|-----|--------|-------|
| api-gateway | 2 cores | 2GB | 8000 |
| redis | 0.25 cores | 256MB | 6379 |
| mediamtx | 0.5 cores | 256MB | 8554 (RTSP), 8889 (WebRTC) |
| nginx | 0.25 cores | 128MB | 80, 443 |

## Tech Stack

| Layer | Technology | Role |
|-------|------------|------|
| Camera | Reolink P340 | H.264 RTSP source |
| Edge | RPi 4 + FFmpeg | Dumb RTSP relay |
| RTSP Server | mediamtx | Ingest + WebRTC serving |
| Backend | FastAPI (Python 3.11+) | API, attendance engine, pipeline manager |
| Face Detection | SCRFD (InsightFace) | Multi-face detection |
| Face Recognition | ArcFace (InsightFace) | 512-dim embeddings |
| Face Search | FAISS IndexFlatIP | Cosine similarity search |
| Tracking | ByteTrack (supervision) | Frame-to-frame tracking with Kalman prediction |
| Cache | Redis 7 | Shared identity cache, pipeline state |
| Database | Supabase PostgreSQL | Users, attendance, schedules |
| Auth | Supabase Auth | JWT, email verification |
| Mobile | React Native (Expo) | Student + Faculty apps |
| Video Delivery | WebRTC (WHEP via mediamtx) | Low-latency annotated stream |
| Deployment | Docker Compose + Nginx | VPS orchestration |

## Migration from Current Codebase

| Component | Current State | After Redesign |
|-----------|---------------|----------------|
| `presence_service.py` | Reads pipeline Redis state, coupled to pipeline | Becomes the attendance engine — grabs own frames, fully independent |
| `video_pipeline.py` | Does everything (attendance + video) | Visual-only — detection, tracking, annotation. No DB writes |
| `recognition_service.py` | Complex state machine with reconnect logic | Simplified or removed — attendance engine handles recognition |
| `pipeline_manager.py` | Manages pipelines as attendance source | Manages pipelines as visual feed only |
| `rtsp_reader.py` | Used by pipeline only | Also used as pattern for FrameGrabber |
| `ffmpeg_publisher.py` | Pipe deadlock bugs, no backpressure | Fix buffer management, add health checks |
| `docker-compose.prod.yml` | References non-existent workers | Clean 4-container setup |
| `config.py` | 15+ dead settings (HLS, batch, legacy stream) | Pruned to active settings only |
| Mobile WebRTC | Complex reconnect state machine | Simplified connect/disconnect |
| Mobile WebSocket | Handler duplication bugs | Clean lifecycle management |
| Mobile face detection | Client-side overlay code | Removed (server handles annotation) |

## Development Parallelism

Steps 1 and 2 can be developed in parallel since they are independent by design:

**Track 1: Attendance Engine**
- FrameGrabber implementation
- Attendance scan cycle (SCRFD + ArcFace + FAISS + DB)
- Redis cache writes
- Miss counter + early-leave detection
- WebSocket notifications

**Track 2: Live Feed Pipeline**
- Fix RTSPReader (timeout on FFmpeg exit, graceful shutdown)
- Fix FFmpegPublisher (backpressure, deadlock prevention)
- Redis cache reads for identity labeling
- Lazy ArcFace loading
- Session-bound lifecycle management

**Track 3: Mobile + Cleanup (after 1 & 2)**
- Remove client-side detection overlay code
- Fix token refresh queue hang
- Fix WebSocket handler duplication
- Fix WebRTC connection leak on unmount
- Relax face registration thresholds
- Clean up docker-compose.prod.yml, config.py, nginx.conf
