# Client-Side Detection Redesign — Design Document

**Date:** 2026-03-19
**Status:** Approved
**Branch:** TBD (new branch from main or current)

## Problem Statement

The current architecture processes video on the VPS backend: decode RTSP at 20fps → detect faces → track with ByteTrack → annotate frames → re-encode H.264 → serve via WebRTC. This creates cascading failures: FFmpeg pipe deadlocks, ByteTrack instability, encoder lag, FAISS corruption under load, and subprocess management complexity. 18+ design docs and 20+ bug-fix commits have failed to stabilize it.

The fundamental flaw: **real-time video processing does not belong on a remote server.**

## Core Insight

Move face detection to the mobile device. The phone has ML Kit, which runs face detection at 30fps on-device with zero network latency. The backend only needs to recognize faces (identify WHO) every 10-15 seconds. Video streams raw from the camera to the phone — the backend never touches video.

## Architecture

```
CAMERA LAYER
  Reolink P340 (RTSP H.264)
       |
       v
  RPi FFmpeg relay (dumb copy, unchanged)
       |
       v
  mediamtx on VPS (RTSP ingest + WebRTC serving)
       |
       +---> WebRTC (WHEP) ──> Kotlin App (ExoPlayer, smooth raw video)
       |                            |
       |                       ML Kit Face Detection (on-device, 30fps)
       |                            |
       |                       Draws bounding boxes in real-time
       |
       +---> Backend FrameGrabber (grabs 1 frame every 10-15s)
                  |
                  v
             SCRFD detect → ArcFace recognize → FAISS match
                  |
                  v
             Write to DB (attendance_records, presence_logs)
                  |
                  v
             WebSocket broadcast:
               - Face identities (name + bbox + confidence)
               - Attendance updates (present/absent/early-leave)
                  |
                  v
             Kotlin App overlays names on ML Kit bounding boxes
```

**Three independent concerns:**

| Concern | Where it runs | Failure impact |
|---------|---------------|----------------|
| Video delivery | mediamtx → WebRTC → phone | If fails: no video, but attendance still works |
| Face detection (boxes) | ML Kit on phone | If fails: no boxes, but video + attendance still work |
| Face recognition (names + attendance) | Backend every 10-15s | If fails: no names/attendance, but video + boxes still work |

## Kotlin Mobile App

**Tech Stack:**

| Layer | Technology |
|-------|------------|
| UI | Jetpack Compose + Material 3 |
| Video | ExoPlayer (Media3) — native RTSP support |
| Face Detection | Google ML Kit Face Detection (on-device) |
| Camera | CameraX (face registration only) |
| API | Retrofit + OkHttp |
| WebSocket | OkHttp WebSocket client |
| DI | Hilt |
| Navigation | Navigation Compose |
| Storage | DataStore (tokens, preferences) |

**Screens (~15 total):**

```
Auth:
  ├─ LoginScreen (students + faculty)
  └─ Registration Wizard
       ├─ Step 1: Verify Student ID
       ├─ Step 2: Create account (name, email, password)
       ├─ Step 3: Face capture (CameraX, 3-5 angles, ML Kit guides positioning)
       └─ Step 4: Review & submit

Student (BottomNav):
  ├─ Home (today's attendance summary, upcoming classes)
  ├─ Schedule (weekly view)
  ├─ History (attendance records)
  └─ Profile (settings, logout)

Faculty (BottomNav):
  ├─ Home (active classes, today's schedule)
  ├─ Live Feed (ExoPlayer + ML Kit overlay + attendance panel)
  ├─ Reports (attendance by class/date)
  └─ Profile (settings, logout)
```

### Live Feed Screen (Key Screen)

Three rendering layers in a Compose `Box`:

1. **Bottom:** ExoPlayer `TextureView` playing RTSP from mediamtx
2. **Middle:** ML Kit face detection overlay (real-time bounding boxes)
3. **Top:** Name labels from WebSocket recognition results

**ML Kit processing flow:**
1. ExoPlayer renders to `TextureView`
2. `onSurfaceTextureUpdated` callback fires on each frame
3. `textureView.getBitmap()` extracts current frame
4. `InputImage.fromBitmap(bitmap, 0)` creates ML Kit input
5. `faceDetector.process(image)` returns `List<Face>` with bounding boxes
6. Draw boxes on transparent Canvas overlay
7. Match backend recognition results (names) to ML Kit faces by position proximity (IoU)

**Throttling:** Process every 2nd-3rd frame to keep CPU usage reasonable (~10-15fps detection is visually smooth).

### Face Registration Screen

Uses the phone's own camera (CameraX), not the classroom camera:

1. CameraX opens front camera
2. ML Kit detects face in real-time (validates face is visible, centered)
3. UI guides: "Look straight" → "Turn slightly left" → "Turn slightly right" → etc.
4. Captures 3-5 images at guided angles
5. Uploads base64 images to `POST /api/v1/face/register`
6. Backend: SCRFD detect → ArcFace embed → average embeddings → store in FAISS

## Simplified Backend

**Structure:**

```
backend/app/
├── main.py              # FastAPI entry, lifespan manages FrameGrabber + scheduler
├── config.py            # Settings (stripped to essentials)
├── database.py          # Supabase/PostgreSQL connection
├── redis_client.py      # Redis for identity cache only
├── models/              # SQLAlchemy models (unchanged)
├── schemas/             # Pydantic schemas (simplified)
├── routers/
│   ├── auth.py          # Login, register, JWT
│   ├── users.py         # User CRUD
│   ├── face.py          # Face registration + FAISS management
│   ├── schedules.py     # Schedule + enrollment CRUD
│   ├── attendance.py    # Attendance records, session start/stop
│   ├── rooms.py         # Room CRUD
│   ├── health.py        # Simple health check
│   └── websocket.py     # Single WebSocket endpoint (attendance + detections)
├── services/
│   ├── auth_service.py
│   ├── face_service.py       # SCRFD + ArcFace + FAISS (register + recognize)
│   ├── attendance_engine.py  # APScheduler job: grab frame → detect → recognize → DB → WS
│   ├── frame_grabber.py      # Persistent RTSP frame source (keep existing FFmpeg version)
│   ├── user_service.py
│   └── enrollment_service.py
├── services/ml/
│   ├── insightface_model.py  # SCRFD + ArcFace wrapper (keep existing)
│   └── faiss_manager.py      # FAISS index management (simplified, single worker)
├── repositories/             # DB queries (keep existing)
└── utils/                    # Security, deps (keep existing)
```

**What gets DELETED:**

| Deleted | Reason |
|---------|--------|
| `pipeline/` directory entirely | No video processing on backend |
| `services/ml/yunet_detector.py` | Detection happens on phone |
| `services/stream_bus.py` | Redis Streams overkill |
| `services/recognition_service.py` | Absorbed into attendance_engine |
| `services/mediamtx_service.py` | mediamtx just runs, no management |
| `services/webrtc_service.py` | WebRTC is mediamtx's job |
| `services/session_scheduler.py` | Simplify to manual session start/stop |
| `services/analytics_service.py` | Not needed for thesis MVP |
| `services/anomaly_service.py` | Not needed for thesis MVP |
| `services/prediction_service.py` | Not needed for thesis MVP |
| `services/engagement_service.py` | Not needed for thesis MVP |
| `services/reenrollment_service.py` | Not needed for thesis MVP |
| `services/notification_service.py` | WebSocket is enough |
| `services/digest_service.py` | Not needed for thesis MVP |
| `services/email_service.py` | Not needed for thesis MVP |
| `services/camera_config.py` | Simplify into config.py |
| `routers/pipeline.py` | No pipeline |
| `routers/live_stream.py` | No server-side live stream |
| `routers/edge_ws.py` | RPi doesn't send frames |
| `routers/webrtc.py` | mediamtx handles WebRTC directly |
| `routers/analytics.py` | Not needed for thesis MVP |
| `routers/audit.py` | Not needed for thesis MVP |
| `routers/edge.py` | RPi monitoring not needed |
| `workers/` directory | No workers |
| `supervision` dependency | No ByteTrack |

### Attendance Engine (The Only Smart Part)

```python
# Runs every 10-15 seconds per active session via APScheduler
async def run_attendance_scan(session_id: str, room_id: str):
    frame = frame_grabber.grab()
    if frame is None:
        return  # skip, retry next interval

    faces = scrfd.detect(frame)  # ~20ms

    detections = []
    for bbox, conf in faces:
        crop = frame[y1:y2, x1:x2]
        embedding = arcface.get_embedding(crop)  # ~10ms
        match = faiss_index.search(embedding, k=1)

        if match.distance >= threshold:
            mark_present(match.user_id, session_id)
            reset_miss_counter(match.user_id)
            detections.append({
                "bbox": normalize(bbox, frame.shape),  # 0-1 range
                "name": match.name,
                "confidence": match.distance,
                "user_id": match.user_id
            })

    # Check for early leave (3 consecutive missed scans)
    for student in enrolled_students:
        if not seen_this_scan(student):
            increment_miss(student)
            if miss_count >= 3:
                flag_early_leave(student)

    # Broadcast to all connected faculty WebSockets
    await broadcast({
        "type": "scan_result",
        "room_id": room_id,
        "session_id": session_id,
        "detections": detections,
        "present_count": len(present),
        "total_enrolled": len(enrolled_students)
    })
```

### WebSocket Protocol

Single WebSocket endpoint: `/api/v1/ws/{user_id}`

**Server → Client messages:**

```json
{
  "type": "scan_result",
  "room_id": "room-1",
  "session_id": "session-uuid",
  "timestamp": 1710680400,
  "detections": [
    {
      "bbox": [0.15, 0.20, 0.35, 0.60],
      "name": "Juan Dela Cruz",
      "confidence": 0.92,
      "user_id": "uuid"
    }
  ],
  "present_count": 5,
  "total_enrolled": 20,
  "absent": ["Maria Torres", "Jose Reyes"],
  "early_leave": []
}
```

```json
{
  "type": "early_leave_alert",
  "student_name": "Pedro Santos",
  "student_id": "2024-0001",
  "session_id": "session-uuid",
  "missed_scans": 3
}
```

**Bbox coordinates are normalized (0-1).** The Kotlin app scales them to match the video view dimensions.

## Docker Compose (Production)

```yaml
services:
  api-gateway:       # FastAPI + attendance engine (no video processing)
    mem_limit: 1.5g  # Much less than before (no video encode/decode)
    cpus: 1.0

  redis:             # Identity cache only
    mem_limit: 128m

  mediamtx:          # RTSP ingest + WebRTC serving
    ports:
      - "8554:8554"       # RTSP ingest from RPi
      - "8889:8889"       # WHEP (WebRTC) for mobile
      - "8887:8887/udp"   # WebRTC UDP

  nginx:             # Reverse proxy
```

No coturn needed if the phone and VPS are on the same network or if mediamtx's built-in TURN is sufficient for the demo environment.

## Local Development

```bash
# Terminal 1: mediamtx
docker run --rm -p 8554:8554 -p 8889:8889 -p 8887:8887/udp bluenviron/mediamtx

# Terminal 2: Fake RTSP source (webcam or video file)
ffmpeg -f avfoundation -i "0" -c:v libx264 -f rtsp rtsp://localhost:8554/test/raw

# Terminal 3: Backend
cd backend && source venv/bin/activate && python run.py

# Terminal 4: Redis
docker run --rm -p 6379:6379 redis:7-alpine

# Android Studio: Run Kotlin app on emulator or USB-connected phone
```

## Migration from Current Codebase

| Current | After |
|---------|-------|
| ~30 service files | ~6 service files |
| Video processing on VPS | Zero video processing on VPS |
| ByteTrack + YuNet + FFmpeg pipeline | Deleted entirely |
| React Native mobile app | Kotlin + Jetpack Compose |
| Detection on backend (network round-trip) | ML Kit on phone (instant) |
| Redis Streams, pub/sub, complex caching | Redis for simple identity cache |
| 5 APScheduler jobs | 1 APScheduler job (attendance scan) |
| ~20 router files | ~8 router files |

## Timeline

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Backend strip-down + Kotlin project setup | Simplified backend, Kotlin app with auth + navigation |
| 2 | ExoPlayer + ML Kit + live feed screen | Real-time face detection on video, face registration |
| 3 | Attendance flow + remaining screens | Full end-to-end attendance tracking |
| 4 | Integration testing, VPS deployment, demo prep | Stable demo on real hardware |

## Known Limitations

1. **Bounding box names update every 10-15 seconds** — ML Kit draws real-time unnamed boxes, names appear after backend recognition. Acceptable for classroom (faces don't change identity mid-class).

2. **ML Kit detects but doesn't recognize** — It only finds faces, it doesn't know WHO. The backend handles identity via ArcFace + FAISS.

3. **Phone must be on same network or have internet** — WebRTC needs connectivity to mediamtx. For demo, campus WiFi is sufficient.

4. **Single room pilot** — Architecture supports multiple rooms but tested with one camera.
