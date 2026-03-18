# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IAMS (Intelligent Attendance Monitoring System) is a CCTV-based facial recognition attendance system for JRMSU. It features:
- Raspberry Pi edge device as a dumb RTSP relay (FFmpeg, no ML)
- mediamtx for RTSP ingestion and WebRTC serving
- FastAPI backend for face recognition (InsightFace ArcFace + FAISS) and attendance tracking
- Kotlin Android app with ExoPlayer (video), ML Kit (on-device face detection), CameraX (face registration)
- Supabase for database (PostgreSQL) and authentication

## Architecture

```
Reolink Camera (RTSP)
       │
       v
RPi (FFmpeg relay, no ML)
       │
       v
mediamtx on VPS (RTSP ingest + WebRTC)
       │
       ├──> WebRTC ──> Kotlin App (ExoPlayer, smooth video)
       │                    │
       │               ML Kit (on-device face detection, 30fps)
       │                    │
       │               Draws real-time bounding boxes
       │
       └──> Backend FrameGrabber (grabs 1 frame every 15s)
                 │
                 v
            SCRFD + ArcFace → FAISS match → DB
                 │
                 v
            WebSocket broadcast (names + bbox) → Kotlin App overlays names
```

**Three independent systems:**
1. **Video delivery** — mediamtx → WebRTC → phone (always smooth, no backend processing)
2. **Face detection** — ML Kit on phone (real-time, 30fps, no network needed)
3. **Attendance** — Backend grabs 1 frame/15s → SCRFD+ArcFace → DB → WebSocket

## Development Commands

### Local Docker Development (Recommended)
```bash
# Start full stack
docker compose up -d

# View logs
docker compose logs -f api-gateway

# Stop
docker compose down

# Rebuild after requirements.txt change
docker compose build --no-cache
```

Docker dev stack: `api-gateway` + `redis` + `mediamtx` (3 services)

**Hot reload:** Backend code is volume-mounted — edit Python files and uvicorn/watchfiles auto-restart.

### Backend (without Docker)
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python run.py                  # Start dev server on port 8000
```

### Testing
```bash
cd backend
pytest                                    # Run all tests
pytest tests/test_auth.py                 # Single test file
pytest -v                                 # Verbose output
pytest --cov=app                          # With coverage
```

### Edge Device (Raspberry Pi)
```bash
cd edge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py
```
The RPi only runs an FFmpeg relay — no ML, no face detection.

### Kotlin Android App
```bash
cd android
./gradlew assembleDebug        # Build debug APK
./gradlew installDebug         # Install on connected device/emulator
```
Open in Android Studio for development. Requires Android SDK 35, min SDK 26.

### Local RTSP Testing (without real camera)
```bash
# Fake RTSP source from webcam
ffmpeg -f avfoundation -i "0" -c:v libx264 -f rtsp rtsp://localhost:8554/test/raw

# Or loop a video file
ffmpeg -stream_loop -1 -re -i test_video.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/test/raw
```

## Key Technical Details

### Face Recognition Pipeline
- **Registration:** CameraX captures 3-5 face angles on phone → upload to backend → SCRFD detect → ArcFace embed → store in FAISS
- **Recognition:** Backend grabs frame → SCRFD detect → ArcFace embed → FAISS search → match if cosine similarity > threshold
- **Model:** InsightFace buffalo_l (SCRFD detection + ArcFace recognition), 512-dim embeddings

### On-Device Face Detection (ML Kit)
- Google ML Kit Face Detection runs at 30fps on the Android phone
- Processes frames from ExoPlayer's TextureView
- Draws real-time bounding boxes (no network round-trip)
- Backend recognition results (names) are matched to ML Kit boxes via IoU

### Continuous Presence Tracking
- Backend scans every 15 seconds during active sessions
- 3 consecutive missed scans triggers early-leave alert
- Presence score = (total_present / total_scans) × 100%

### FAISS Index
- `IndexFlatIP` with 512-dim ArcFace embeddings
- Cosine similarity via inner product on L2-normalized vectors
- Persisted to `data/faiss/faces.index`

## Backend Structure

```
backend/app/
├── main.py           # FastAPI entry + APScheduler (attendance scan every 15s)
├── config.py         # Settings
├── database.py       # PostgreSQL connection
├── redis_client.py   # Redis for identity cache
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic request/response
├── routers/          # API endpoints (auth, face, attendance, schedules, rooms, presence, ws, health)
├── services/
│   ├── auth_service.py
│   ├── face_service.py          # SCRFD + ArcFace + FAISS (register + recognize)
│   ├── attendance_engine.py     # Grab frame → detect → recognize → ScanResult
│   ├── frame_grabber.py         # Persistent RTSP frame source (FFmpeg subprocess)
│   ├── presence_service.py      # Miss counters, early-leave detection, DB writes
│   ├── identity_cache.py        # Redis identity cache
│   └── ml/
│       ├── insightface_model.py # SCRFD + ArcFace wrapper
│       └── faiss_manager.py     # FAISS index management
├── repositories/     # Database queries
└── utils/            # Security, dependencies, exceptions
```

**Pattern:** Routes → Services → Repositories → Models

## Android App Structure

```
android/app/src/main/java/com/iams/app/
├── IAMSApplication.kt          # @HiltAndroidApp
├── MainActivity.kt             # @AndroidEntryPoint, single activity
├── di/NetworkModule.kt          # Hilt: Retrofit, OkHttp, ApiService
├── data/
│   ├── api/
│   │   ├── ApiService.kt       # Retrofit interface (all endpoints)
│   │   ├── AuthInterceptor.kt  # Bearer token interceptor
│   │   ├── TokenManager.kt     # DataStore token persistence
│   │   └── AttendanceWebSocketClient.kt  # OkHttp WebSocket
│   └── model/Models.kt         # All data classes
└── ui/
    ├── theme/                   # Material 3 monochrome theme
    ├── navigation/              # Routes, NavHost, NavViewModel
    ├── components/
    │   ├── RtspVideoPlayer.kt   # ExoPlayer RTSP composable
    │   ├── FaceDetectionProcessor.kt  # ML Kit on TextureView frames
    │   ├── FaceOverlay.kt       # Canvas overlay with IoU name matching
    │   ├── FaceCaptureView.kt   # CameraX face registration
    │   └── IAMSBottomBar.kt     # Bottom navigation
    ├── auth/                    # Login, Registration (4 steps), Email verification
    ├── student/                 # Home, Schedule, History, Profile
    └── faculty/                 # Home, Live Feed (crown jewel), Reports, Profile
```

**Tech Stack:** Kotlin + Jetpack Compose + Material 3, ExoPlayer (Media3), ML Kit Face Detection, CameraX, Retrofit + OkHttp, Hilt, Navigation Compose, DataStore

## Database Schema (core tables)

- `users` - All system users with role (student/faculty/admin)
- `face_registrations` - Links users to FAISS embedding IDs
- `face_embeddings` - Individual embedding vectors per user
- `rooms` - Classroom locations with camera endpoints
- `schedules` - Class schedules (subject, faculty, room, time)
- `enrollments` - Student-schedule relationships
- `attendance_records` - Check-in records
- `presence_logs` - Periodic scan results
- `early_leave_events` - Early leave detections

## API Conventions

- Base URL: `/api/v1`
- Auth: `Authorization: Bearer <jwt_token>`
- WebSocket: `/api/v1/ws/attendance/{schedule_id}` (scan results with normalized bbox)
- WebSocket: `/api/v1/ws/alerts/{user_id}` (early-leave alerts)

## WebSocket Protocol

Server broadcasts after each attendance scan:
```json
{
  "type": "scan_result",
  "schedule_id": "uuid",
  "detections": [
    {"bbox": [0.15, 0.20, 0.35, 0.60], "name": "Juan Dela Cruz", "confidence": 0.92, "user_id": "uuid"}
  ],
  "present_count": 5,
  "total_enrolled": 20,
  "absent": ["Maria Torres"],
  "early_leave": []
}
```
Bbox coordinates are normalized (0-1). The Kotlin app matches them to ML Kit detections via IoU.

## User Flows

**Students:** Self-register (verify Student ID → create account → email verification → capture 3-5 face angles with CameraX → review)

**Faculty:** Pre-seeded accounts only. Login → view today's classes → open Live Feed (ExoPlayer + ML Kit + attendance panel)

## Environment Variables

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=xxxxx...
DATABASE_URL=postgresql://user:pass@host/db
JWT_SECRET_KEY=xxxxx...
REDIS_URL=redis://localhost:6379/0
```

## Production Deployment (DigitalOcean VPS)

The backend runs on a DigitalOcean droplet at `167.71.217.44`.

### Deploy command
```bash
bash deploy/deploy.sh
```

### Production stack
- `api-gateway` — FastAPI + attendance engine (1.5GB, 1 CPU)
- `redis` — identity cache (128MB)
- `mediamtx` — RTSP/WebRTC relay
- `nginx` — reverse proxy + SSL

### What triggers a deploy prompt
Any change to files under `backend/` should prompt: "Do you want to deploy this to the VPS?"

## Documentation

- Design doc: `docs/plans/2026-03-19-client-side-detection-redesign-design.md`
- Implementation plan: `docs/plans/2026-03-19-client-side-detection-redesign-plan.md`
- Detailed docs in `/docs/main/` (prd, architecture, api-reference, database-schema, implementation)
