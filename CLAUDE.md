# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IAMS (Intelligent Attendance Monitoring System) is a CCTV-based facial recognition attendance system for JRMSU. It features:
- Raspberry Pi edge device as a dumb RTSP relay (FFmpeg, no ML)
- mediamtx for RTSP ingestion and WebRTC serving
- FastAPI backend for face recognition (InsightFace ArcFace + FAISS) and attendance tracking
- Kotlin Android app with ExoPlayer (video), ML Kit (on-device face detection), CameraX (face registration)
- PostgreSQL database (runs on VPS via Docker)
- React + Vite admin portal

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
       └──> Backend FrameGrabber (grabs frames at 10fps)
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
3. **Attendance** — Backend grabs frames at 10fps → SCRFD+ArcFace+ByteTrack → DB → WebSocket

## Development Workflow — VPS-First

All development targets the DigitalOcean VPS at `167.71.217.44`. Local Docker Desktop is NOT used.

### Deploy Backend Changes
```bash
bash deploy/deploy.sh
```
This rsyncs code, rebuilds the Docker image, and restarts the api-gateway on the VPS.
Backend auto-restarts on code sync (uvicorn watchfiles).

### View VPS Logs
```bash
# Live logs
ssh root@167.71.217.44 "docker logs -f iams-api-gateway"

# Recent logs (last 5 minutes)
ssh root@167.71.217.44 "docker logs --since 5m iams-api-gateway"

# Web UI (Dozzle)
# http://167.71.217.44:9999
```

### Run Commands on VPS
```bash
# Run a Python command inside the backend container
ssh root@167.71.217.44 "docker exec iams-api-gateway python -c 'print(1)'"

# Run tests
ssh root@167.71.217.44 "docker exec iams-api-gateway python -m pytest tests/ -q"

# Django-style shell
ssh root@167.71.217.44 "docker exec -it iams-api-gateway python"
```

### Database Reset & Seed
```bash
ssh root@167.71.217.44 "docker exec iams-api-gateway python -m scripts.seed_data"
```

When asked to "seed the data" or "reset the database", run the command above.

This wipes ALL data and reseeds from scratch: ~160 student records, 2 faculty accounts
(`faculty.eb226@gmail.com`, `faculty.eb227@gmail.com`, password: `password123`),
admin (`admin@admin.com` / `123`), rooms, schedules, and system settings.

### Database Queries (Direct SQL)
```bash
ssh root@167.71.217.44 "docker exec iams-postgres psql -U iams -d iams -c 'SELECT count(*) FROM users;'"
```

### Testing
```bash
ssh root@167.71.217.44 "docker exec iams-api-gateway python -m pytest tests/ -q"
ssh root@167.71.217.44 "docker exec iams-api-gateway python -m pytest tests/ -q -k 'faiss or tracker'"
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
- Backend runs real-time pipeline at 10fps during active sessions
- Configurable early-leave timeout per schedule (default from settings)
- Presence score = (total_present / total_scans) × 100%

### FAISS Index
- `IndexFlatIP` with 512-dim ArcFace embeddings
- Cosine similarity via inner product on L2-normalized vectors
- Persisted to `data/faiss/faces.index`

## Backend Structure

```
backend/app/
├── main.py           # FastAPI entry + APScheduler + on-demand pipeline startup
├── config.py         # Settings
├── database.py       # PostgreSQL connection
├── redis_client.py   # Redis for identity cache
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic request/response
├── routers/          # API endpoints (auth, face, attendance, schedules, rooms, presence, ws, health)
├── services/
│   ├── auth_service.py
│   ├── face_service.py          # SCRFD + ArcFace + FAISS (register + recognize)
│   ├── realtime_tracker.py      # ByteTrack + cached ArcFace recognition (10fps)
│   ├── realtime_pipeline.py     # Session pipeline orchestrator (frame → track → broadcast)
│   ├── track_presence_service.py # Presence tracking, early-leave detection
│   ├── attendance_engine.py     # Legacy single-frame scanner
│   ├── frame_grabber.py         # Persistent RTSP frame source (FFmpeg subprocess)
│   ├── presence_service.py      # Session lifecycle, presence logging
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

## Admin Portal Structure

```
admin/
├── src/
│   ├── components/        # Reusable UI components (Radix UI + Tailwind)
│   ├── pages/             # Route pages (Dashboard, Users, Schedules, etc.)
│   ├── services/          # API client (Axios)
│   ├── stores/            # Zustand state management
│   └── hooks/             # Custom React hooks
├── .env                   # VITE_API_URL, VITE_WS_URL (points to VPS)
└── vite.config.ts         # Dev server proxy config
```

**Tech Stack:** React 19 + Vite + TypeScript, Radix UI + Tailwind CSS, TanStack Query, Zustand, Recharts

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

Backend env vars are in `backend/.env` (local) and VPS `/opt/iams/deploy/.env` (production).
Key variables:
```
DATABASE_URL=postgresql://iams:password@postgres:5432/iams
JWT_SECRET_KEY=xxxxx...
REDIS_URL=redis://:iams-redis-dev@redis:6379/0
RESEND_API_KEY=xxxxx...     # Email service
```

## VPS Infrastructure (DigitalOcean)

**IP:** `167.71.217.44` — all services run here.

### Production stack (Docker Compose)
| Container | Image | Purpose |
|-----------|-------|---------|
| `iams-api-gateway` | Custom (Python 3.11) | FastAPI + attendance engine |
| `iams-postgres` | postgres:16-alpine | PostgreSQL database |
| `iams-redis` | redis:7-alpine | Identity cache (128MB) |
| `iams-mediamtx` | bluenviron/mediamtx:1.11.3 | RTSP ingest + WebRTC relay |
| `iams-nginx` | nginx:alpine | Reverse proxy + SSL |
| `iams-coturn` | coturn/coturn | TURN server for WebRTC NAT traversal |
| `iams-dozzle` | amir20/dozzle | Log viewer (port 9999) |

### URLs
- **Admin Portal:** https://iams-thesis.vercel.app (deployed on Vercel)
- **API:** http://167.71.217.44/api/v1
- **API Docs:** http://167.71.217.44/api/v1/docs
- **Health:** http://167.71.217.44/api/v1/health
- **Logs:** http://167.71.217.44:9999

### Deploy
```bash
bash deploy/deploy.sh
```

### What triggers a deploy
Any change to files under `backend/` should prompt: "Do you want to deploy this to the VPS?"
Always deploy after making backend changes — there is no local environment.

## Plan Mode: Lesson Capture

Every plan must end with a `## Lessons` section containing insights discovered during planning — things like "never do X", "Y breaks because Z", or "always check W first". These are written in the plan file during planning (read-only is fine — it's part of the plan).

**After exiting plan mode**, the first execution step is always: write any lessons from the plan's `## Lessons` section to `memory/lessons.md`. This ensures planning insights survive into execution and future sessions.

Format in `memory/lessons.md`:
```
## YYYY-MM-DD: Short title
What happened, why it matters, what to do differently.
```

## Documentation

- Design doc: `docs/plans/2026-03-19-client-side-detection-redesign-design.md`
- Implementation plan: `docs/plans/2026-03-19-client-side-detection-redesign-plan.md`
- Detailed docs in `/docs/main/` (prd, architecture, api-reference, database-schema, implementation)
