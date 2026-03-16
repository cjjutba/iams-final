# RTSP-Direct + Server-Side Compositing Architecture Redesign

**Date:** 2026-03-17
**Status:** Approved
**Supersedes:** All previous pipeline/tracking/streaming designs

## Problem Statement

The current architecture has fundamental flaws that produce a buggy, laggy, desynchronized experience:

1. **3 FPS frame sampling** — JPEG snapshots at 3 FPS, Base64-encoded (+33% bloat), JSON-wrapped, pushed over WebSocket
2. **9 hops to display** — RPi → WebSocket → Redis Stream → detection-worker → Redis → recognition-worker → Redis → TrackFusion → WebSocket → mobile overlay
3. **Permanent video/overlay desync** — live video arrives via WebRTC (Path A), detection metadata arrives via WebSocket (Path B). Different transport latencies = boxes never align with faces
4. **SimpleTracker (IoU-only)** — no two-pass association, tracks swap IDs on occlusion
5. **JS-thread bounding box animation** — `useNativeDriver: false` on all overlay animations, freezes UI at 50+ faces
6. **Broken legacy code** — `presence_service.feed_detection()` doesn't exist, `room.stream_key` vs `room_id` UUID mismatch

## Solution: Enterprise RTSP-Direct + Server-Side Compositing

Follow the industry standard pattern used by NVIDIA DeepStream, Hikvision Smart NVR, Milestone XProtect, and Frigate NVR:

1. Backend reads RTSP stream directly from mediamtx (not WebSocket frame push)
2. Single unified pipeline: detect → track → recognize → annotate
3. Bounding boxes burned INTO the video frames (server-side compositing)
4. Annotated stream re-published to mediamtx as a new RTSP path
5. Mobile app just plays a WebRTC video — zero overlay code

## Constraints

- **Production:** DigitalOcean 4 vCPU / 8GB RAM, CPU-only, $48/mo
- **Development:** MacBook Pro M4 Pro 24GB RAM
- **Cameras:** 2 concurrent Reolink P340 (RTSP sub-stream, H.264, 640x480)
- **Faces:** Up to 50 per room
- **Bounding boxes:** Visual indicators only, non-interactive

## Architecture

### Current (Broken)

```
RPi → JPEG@3FPS → Base64 JSON → WebSocket → Redis → Detection Worker → Redis
→ Recognition Worker → Redis → TrackFusion → Redis → WebSocket → Mobile (JS overlay)
```

### New (Enterprise)

```
RPi → FFmpeg relay → mediamtx/{room_id}/raw
                           ↓ (RTSP read)
                  VideoAnalyticsPipeline
                  (detect → track → recognize → annotate)
                           ↓ (FFmpeg encode)
                  mediamtx/{room_id}/annotated
                           ↓ (WebRTC WHEP)
                  Mobile app (just plays video)
```

### Data Flow Diagram

```
Reolink P340 Camera
        │
        │  RTSP sub-stream (H.264, 640x480)
        │
        ▼
[Edge: StreamRelay] ─── FFmpeg -c copy ───▶ [mediamtx :8554/{room_id}/raw]
                                                      │
                                                      │ RTSP (read by OpenCV threaded reader)
                                                      ▼
                                          ┌───────────────────────────┐
                                          │  VideoAnalyticsPipeline   │
                                          │                           │
                                          │  SCRFD_500M  (detect)     │
                                          │       ↓                   │
                                          │  ByteTrack   (track)      │
                                          │       ↓                   │
                                          │  ArcFace     (recognize)  │
                                          │       ↓                   │
                                          │  Annotator   (draw)       │
                                          │       ↓                   │
                                          │  FFmpeg      (encode+push)│
                                          └───────────┬───────────────┘
                                                      │
                                    ┌─────────────────┼────────────────┐
                                    ▼                 ▼                ▼
                          mediamtx/annotated    Redis (state)    Redis (attendance)
                                    │                 │                │
                                    │ WebRTC          │ poll           │ pub/sub
                                    ▼                 ▼                ▼
                              Mobile App         FastAPI API     Attendance WS
                           (plays video)      (health, mgmt)   (text data only)
```

## Components Removed

| Component | Reason |
|-----------|--------|
| `edge/app/frame_sampler.py` | Backend reads RTSP directly |
| `edge/app/main.py` (WebSocket loop) | No more frame shipping |
| `stream:frames` Redis Streams | No frame transport needed |
| `detection-worker` container | Merged into VideoAnalyticsPipeline |
| `recognition-worker` container | Merged into VideoAnalyticsPipeline |
| `backend/app/services/track_fusion_service.py` | Replaced by ByteTrack |
| `backend/app/workers/detection_worker.py` | Merged into pipeline |
| `backend/app/workers/recognition_worker.py` | Merged into pipeline |
| `mobile/src/engines/TrackAnimationEngine.ts` | No overlay needed |
| `mobile/src/components/video/DetectionOverlay.tsx` | No overlay needed |
| `mobile/src/hooks/useDetectionWebSocket.ts` (detection path) | No detection metadata to mobile |
| `mobile/src/hooks/useDetectionTracker.ts` | Legacy, already unused |
| `computeScale` coordinate conversion | No coordinate mapping needed |
| Broken `feed_detection()` / `handle_face_gone()` calls | Dead code path eliminated |

## Components Kept

| Component | Notes |
|-----------|-------|
| `edge/app/stream_relay.py` | Already works, FFmpeg RTSP relay |
| mediamtx | Now serves both raw + annotated streams |
| `mobile/src/hooks/useWebRTC.ts` | Points to annotated stream |
| Attendance WebSocket (`/ws/attendance/{scheduleId}`) | Text-only, lightweight |
| Alerts WebSocket (`/ws/alerts/{userId}`) | Text-only, lightweight |
| Face registration flow | Unchanged (keeps buffalo_l / SCRFD_10G for accuracy) |
| FAISS index + multi-embedding storage | Unchanged |
| Supabase database | Unchanged |
| Presence scoring + early leave logic | Reads from pipeline via Redis |

## New Components

### 1. VideoAnalyticsPipeline

Unified per-room pipeline running as a separate process.

**Subcomponents:**
- `RTSPReader`: Threaded OpenCV capture, always holds latest frame, drops stale frames
- `SCRFD_500M`: Lightweight face detector via ONNX Runtime (~25-35ms CPU, ~5-10ms M4 Pro)
- `ByteTrack`: Multi-object tracker via `supervision` library (~1-2ms for 50 faces)
- `ArcFace`: Face recognizer via ONNX Runtime, lazy — only on new/unidentified tracks
- `FrameAnnotator`: OpenCV drawing — corner brackets, labels, HUD bars (~3-5ms)
- `FFmpegPublisher`: Subprocess stdin pipe → H.264 ultrafast → mediamtx RTSP

**Recognition strategy:**
- New track confirmed (3 consecutive frames) → crop face → ArcFace embedding → FAISS search
- Match found → cache identity in memory, never re-recognize unless explicitly requested
- Re-verification every 60 seconds (optional, configurable)

### 2. PipelineManager

Manages pipeline lifecycle from FastAPI.
- Start/stop pipelines per room (triggered by session start/end)
- Health monitoring via Redis heartbeats (5-second interval, 30-second expiry)
- Auto-restart on failure with exponential backoff
- Exposes pipeline status via existing health check endpoint

### 3. FrameAnnotator

**Visual style:** Corner bracket bounding boxes (enterprise standard)

**Color coding:**
| State | Color (BGR) | Meaning |
|-------|-------------|---------|
| Green `(0, 200, 0)` | Recognized | Matched student |
| Yellow `(0, 200, 255)` | Unknown | Detected, not matched |
| Cyan `(255, 200, 0)` | New | Just appeared, confirming |
| Gray `(128, 128, 128)` | Lost | Temporarily lost track |
| Red `(0, 0, 255)` | Alert | Early leave flagged |

**Labels:**
- Recognized: `"Juan Dela Cruz (2021-0145)"` + `"95% | T#7 | 2m15s"`
- Unknown: `"Unknown Face"` + `"T#12 | 0:05s"`

**HUD bars:**
- Top: `"IAMS | Room 301 - CS Lab"` + timestamp (semi-transparent black)
- Bottom: `"CS101 - Intro to Programming | Prof. Santos | 23/35 Present"`

### 4. FFmpegPublisher

**Encoding settings:**
```
-c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p
-bf 0 -g 50 -b:v 800k -maxrate 1000k -bufsize 500k
-f rtsp -rtsp_transport tcp rtsp://mediamtx:8554/{room_id}/annotated
```

**Mac development:** Uses `h264_videotoolbox -realtime 1` for 4x faster encoding.

**Critical:** `-bf 0` (no B-frames) is required for WebRTC browser compatibility.

## Detection Model Strategy

| Use Case | Model | Input | Performance |
|----------|-------|-------|-------------|
| Real-time pipeline | SCRFD_500M | 640x480 | ~25-35ms CPU, ~5-10ms M4 |
| Face registration | SCRFD_10G (buffalo_l) | 640x640 | Higher accuracy for enrollment |
| Recognition | ArcFace ResNet50 (buffalo_l) | 112x112 crop | ~15-25ms per face, lazy |

## ByteTrack Configuration

```python
tracker = sv.ByteTrack(
    track_activation_threshold=0.20,  # Low: catch partial faces in rows
    lost_track_buffer=90,             # 3 sec at 30fps
    minimum_matching_threshold=0.7,   # Relaxed for seated students
    frame_rate=30,
    minimum_consecutive_frames=3,     # Suppress false positives
)
```

**Why ByteTrack:**
- Two-pass association recovers occluded faces (low-confidence detections)
- ~720 FPS tracking speed on CPU — essentially free
- No ReID network needed (ArcFace handles identity downstream)
- Perfect for fixed-camera, mostly-static seated students

## Performance Budget

### Per Camera (4 vCPU production)

| Stage | Latency | CPU |
|-------|---------|-----|
| SCRFD_500M @ 640x480 | ~30ms | ~0.7 cores |
| ByteTrack (50 faces) | ~1ms | negligible |
| ArcFace (amortized) | ~2ms | ~0.1 cores |
| FrameAnnotator (50 faces) | ~4ms | negligible |
| FFmpeg encode (ultrafast) | ~10ms | ~0.25 cores |
| **Total** | **~38ms = ~26 FPS** | **~1 core** |

### System Total (2 cameras)

| Container | CPU | RAM |
|-----------|-----|-----|
| video-pipeline (2 cameras) | ~2.0 cores | ~1.5GB |
| api-gateway | ~0.5 cores | ~1.0GB |
| redis | ~0.25 cores | 256MB |
| mediamtx | ~0.25 cores | 256MB |
| **Total** | **~3.0 cores** | **~3.0GB** |

Fits within 4 vCPU / 8GB with headroom.

### M4 Pro Development

| Stage | Latency (CoreML) |
|-------|-------------------|
| SCRFD_500M @ 640x480 | ~5-10ms |
| ByteTrack | ~1ms |
| ArcFace (amortized) | ~3-5ms per face |
| FrameAnnotator | ~3ms |
| VideoToolbox encode | ~3ms |
| **Total** | **~15ms = ~60+ FPS** |

## End-to-End Latency

| Stage | Latency |
|-------|---------|
| Camera capture + internal encode | ~50ms |
| RTSP transport (RPi → VPS) | ~20-50ms |
| mediamtx receive | ~10ms |
| RTSP read (OpenCV threaded) | ~5ms |
| Pipeline processing | ~38ms |
| RTSP publish to mediamtx | ~5ms |
| mediamtx remux → WebRTC | ~20ms |
| Network to mobile | ~20-50ms |
| **Total** | **~200-450ms** |

Current system: 1-3 seconds with frequent desyncs. New system: ~300ms average with perfectly synced boxes.

## Docker Compose (Simplified)

### Before: 5 app containers
```
api-gateway + detection-worker + recognition-worker + redis + mediamtx
```

### After: 3 app containers
```yaml
services:
  api-gateway:       # FastAPI + PipelineManager + attendance/presence
  video-pipeline:    # VideoAnalyticsPipeline (handles all rooms)
  redis:             # State + messaging
  mediamtx:          # RTSP ingest + WebRTC serving
```

## Mobile App (Simplified)

### Before
```
WebRTC (raw video) + WebSocket (detection JSON) + TrackAnimationEngine (spring physics)
+ DetectionOverlay (coordinate conversion + letterbox) + useNativeDriver:false (JS thread)
```

### After
```
WebRTC (annotated video with boxes in it) + WebSocket (attendance text data)
```

FacultyLiveFeedScreen becomes: `<RTCView>` + `<AttendancePanel>`. No overlay. No animation engine. No coordinate conversion.

## Edge Device (Simplified)

### Before
StreamRelay (FFmpeg) + FrameSampler (OpenCV + Base64) + WebSocket client + Queue manager

### After
StreamRelay (FFmpeg) + health endpoint. ~50 lines of Python.

**Dependencies removed:** `opencv-python-headless`, `websockets`
**Dependencies kept:** `psutil`, `python-dotenv`

## Resilience

### Pipeline auto-recovery
- RTSP source dies → OpenCV returns None → retry with backoff (5, 10, 20, 30s max)
- FFmpeg publisher dies → BrokenPipeError → restart subprocess within 1-2s
- Pipeline process dies → PipelineManager watchdog restarts via heartbeat timeout (30s)
- Docker restart policy covers container-level crashes

### Health monitoring
Pipeline publishes to Redis every 5 seconds:
```json
{
    "ts": 1710648930.5,
    "fps": 25.3,
    "tracks": 23,
    "identified": 21,
    "status": "running"
}
```

## Communication: Pipeline ↔ FastAPI

Redis is the sole communication channel:

| Direction | Mechanism | Data |
|-----------|-----------|------|
| Pipeline → FastAPI | Redis hash `pipeline:{room_id}:state` | Current tracks, identified users, FPS |
| Pipeline → FastAPI | Redis pub/sub `pipeline:{room_id}:events` | New identification, track lost, alerts |
| FastAPI → Pipeline | Redis pub/sub `pipeline:{room_id}:commands` | Start, stop, reconfigure |
| Pipeline → FastAPI | Redis hash `pipeline:{room_id}:heartbeat` | Health status (5s interval, 30s TTL) |

Presence service reads `pipeline:{room_id}:state` every 60 seconds for attendance scanning (same interval as before, same scoring logic).
