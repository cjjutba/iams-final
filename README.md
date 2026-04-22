# IAMS — Intelligent Attendance Monitoring System

A CCTV-based facial recognition attendance system built for Jose Rizal Memorial State University (JRMSU). IAMS automates student attendance through continuous presence tracking, real-time early-leave detection, and WebRTC live video streaming — all without students needing to do anything beyond registering their face once.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [System Components](#system-components)
  - [Backend (FastAPI)](#backend-fastapi)
  - [Edge Device (Raspberry Pi)](#edge-device-raspberry-pi)
  - [Android App (Kotlin)](#android-app-kotlin)
  - [Admin Dashboard (React)](#admin-dashboard-react)
- [Face Recognition Pipeline](#face-recognition-pipeline)
- [Presence Tracking & Early-Leave Detection](#presence-tracking--early-leave-detection)
- [Live Video Streaming](#live-video-streaming)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Environment Variables](#environment-variables)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [Hardware Requirements](#hardware-requirements)
- [Documentation](#documentation)

---

## Overview

IAMS replaces manual roll calls with an automated system: a Raspberry Pi camera watches the classroom, detects faces with MediaPipe, and sends them to the backend. The backend recognizes faces with InsightFace (ArcFace), tracks presence every 60 seconds, and fires alerts when a student leaves early. Faculty and students interact with the system through a native Android app (Kotlin + Jetpack Compose); admins use a web dashboard.

**Pilot target:** JRMSU Computer Engineering classrooms. Students use their own phones.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Classroom                                          │
│  ┌─────────────────────────────────────────────────────┐                  │
│  │  Raspberry Pi 4                                      │                  │
│  │  ┌──────────┐   MediaPipe     ┌───────────────────┐ │                  │
│  │  │  Camera  │ ─── detect ──▶  │  Edge App (Python) │ │                  │
│  │  └──────────┘                 │  • Queue manager  │ │                  │
│  │                               │  • Smart sampler  │ │                  │
│  │                               │  • RTSP relay     │ │                  │
│  │                               └────────┬──────────┘ │                  │
│  └────────────────────────────────────────┼────────────┘                  │
└───────────────────────────────────────────┼────────────────────────────────┘
                               HTTP POST (Base64 JPEG)
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  DigitalOcean VPS (167.71.217.44)                                         │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  FastAPI Backend (Docker)                                         │     │
│  │                                                                   │     │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │     │
│  │  │  InsightFace │  │ FAISS Index  │  │  APScheduler (60s)     │  │     │
│  │  │  (ArcFace)  │  │ (IndexFlatIP)│  │  • Presence scans      │  │     │
│  │  └─────────────┘  └──────────────┘  │  • Session management  │  │     │
│  │                                     │  • Daily/weekly digests │  │     │
│  │  ┌──────────────────────────────┐   └────────────────────────┘  │     │
│  │  │  WebSocket Manager           │                                │     │
│  │  │  (Redis pub/sub multi-worker)│                                │     │
│  │  └──────────────────────────────┘                                │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────────────────────────┐ │
│  │  Redis     │  │  mediamtx   │  │  Coturn (TURN relay)               │ │
│  │  (pub/sub  │  │  RTSP→WHEP  │  │  (WebRTC NAT traversal)           │ │
│  │   + cache) │  │  WebRTC     │  └────────────────────────────────────┘ │
│  └────────────┘  └─────────────┘                                         │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Nginx (reverse proxy + TLS)                                      │     │
│  │  → /api/*    → backend:8000                                       │     │
│  │  → /admin/*  → static React build                                 │     │
│  │  → /whep/*   → mediamtx:8889                                      │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────────┘
                                  │               │
                    ┌─────────────┘               └──────────────┐
                    ▼                                             ▼
        ┌──────────────────────┐                ┌──────────────────────────┐
        │  Supabase (managed)  │                │  Native Android App      │
        │  PostgreSQL + Auth   │                │  (Kotlin + Compose)      │
        │  (cloud hosted)      │                │  • Student + Faculty     │
        └──────────────────────┘                └──────────────────────────┘
                                                ┌──────────────────────────┐
                                                │  Admin Dashboard (React) │
                                                │  • Vite + shadcn/ui      │
                                                │  • Served by Nginx       │
                                                └──────────────────────────┘
```

**Two-tier design:** The edge device handles detection only (fast, lightweight). The backend handles recognition, tracking, and all business logic (GPU-accelerated on the VPS).

---

## Features

### Core
- **Automatic attendance marking** — face recognition fires when a student enters the room
- **Continuous presence tracking** — scans every 60 seconds during class; no student action needed
- **Early-leave detection** — 3 consecutive missed scans triggers an alert to faculty and the student
- **Session-aware scanning** — edge device polls for active class sessions and only scans during class time
- **Offline queue** — RPi buffers up to 500 face payloads with 5-minute TTL and retries every 10 seconds

### Face Recognition
- **InsightFace (ArcFace / buffalo_l model)** — state-of-the-art recognition accuracy
- **FAISS IndexFlatIP** — cosine similarity search across all registered embeddings
- **Anti-spoofing** — LBP texture + FFT high-frequency energy checks block photo attacks
- **Face quality gating** — blur detection, brightness check, minimum face size enforced
- **Adaptive threshold** — recognition confidence threshold auto-adjusts based on recent match statistics
- **Re-enrollment monitoring** — flags users whose recognition scores degrade over time

### Mobile App
- **Student self-registration** — verify Student ID → create account → capture 3–5 face angles → review
- **Faculty pre-seeded accounts** — no self-registration; login via email + password
- **Real-time notifications** — WebSocket push for attendance marked, early-leave alerts, digest summaries
- **Live attendance view** — faculty see who is present/absent in real time
- **Live video feed** — WebRTC (<300 ms) or HLS fallback for faculty monitoring
- **Manual attendance entry** — faculty override for edge cases

### Admin Dashboard
- **User management** — CRUD for students, faculty, and admins
- **Schedule management** — create and assign class schedules to rooms
- **Analytics** — attendance rates, engagement scores, anomaly detection, at-risk students
- **Edge device monitoring** — heartbeat status, last-seen timestamps
- **Audit logs** — full history of system actions
- **Notification center** — view and manage all system notifications
- **System settings** — configure thresholds, email, feature flags

### Infrastructure
- **WebRTC live streaming** — mediamtx bridges RPi RTSP → WHEP; Coturn provides TURN relay
- **HLS fallback** — FFmpeg-based 0.2 s segment HLS for networks that block WebRTC
- **Multi-worker Redis pub/sub** — WebSocket broadcasts work across Uvicorn workers
- **Daily + weekly digests** — emailed summaries via Resend API (8 PM Manila for faculty, Monday 8 AM for students)
- **Rate limiting** — slowapi guards auth endpoints (10 req/min default)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Edge device | Raspberry Pi 4 · MediaPipe (TFLite) · picamera2 / OpenCV · Python 3.11 |
| Backend | FastAPI 0.128 · Python 3.11 · Uvicorn · APScheduler · slowapi |
| Face recognition | InsightFace (buffalo_l / ArcFace) · FAISS IndexFlatIP · ONNX Runtime |
| Database | PostgreSQL via Supabase · SQLAlchemy 2.0 · Alembic migrations |
| Auth | Custom JWT (HS256) · bcrypt · GoTrue Admin API (Supabase) |
| Cache / pub-sub | Redis 7 (hiredis) |
| Video streaming | mediamtx (RTSP→WHEP) · Coturn (TURN) · FFmpeg (HLS fallback) |
| Android app | Kotlin · Jetpack Compose · Material 3 · ExoPlayer (Media3) · ML Kit Face Detection · CameraX · Retrofit + OkHttp · Hilt · Navigation Compose · DataStore |
| Admin dashboard | React 18 · Vite · TypeScript · shadcn/ui · TanStack Query · Recharts |
| Deployment | Docker + Docker Compose · Nginx · DigitalOcean VPS · Certbot (HTTPS) |
| Email | Resend API |
| Linting | Ruff · mypy (backend) · ESLint (frontend) |

---

## Project Structure

```
iams/
├── backend/                  # FastAPI server
│   ├── app/
│   │   ├── main.py           # App entry, middleware, router registration, scheduler
│   │   ├── config.py         # Pydantic settings (all env vars)
│   │   ├── database.py       # SQLAlchemy engine + SessionLocal
│   │   ├── models/           # SQLAlchemy ORM models (20 tables)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── routers/          # API endpoint handlers (16 routers)
│   │   ├── services/         # Business logic (face, presence, tracking, etc.)
│   │   │   └── ml/           # InsightFace model + FAISS manager
│   │   ├── repositories/     # Database query layer
│   │   └── utils/            # Security, dependencies, exceptions
│   ├── alembic/              # Database migrations
│   ├── scripts/              # seed_data.py, seed_school_data.py, wipe_user_data.py
│   ├── tests/                # pytest test suite
│   ├── Dockerfile            # Multi-stage Docker build
│   ├── requirements.txt
│   └── run.py                # Development entry point
│
├── edge/                     # Raspberry Pi edge device
│   ├── app/
│   │   ├── main.py           # EdgeDevice class, main scan loop
│   │   ├── config.py         # Edge configuration (env vars)
│   │   ├── camera.py         # CameraManager (picamera2 / USB / RTSP)
│   │   ├── detector.py       # MediaPipe face detection
│   │   ├── processor.py      # Face cropping + JPEG encoding
│   │   ├── sender.py         # HTTP client (send to backend)
│   │   ├── queue_manager.py  # Offline queue + RetryWorker
│   │   ├── smart_sampler.py  # IoU-based dedup (avoid resending same face)
│   │   └── stream_relay.py   # FFmpeg RTSP→VPS relay (for WebRTC)
│   ├── scripts/              # Utility scripts
│   └── requirements.txt
│
├── android/                  # Native Android app (Kotlin + Jetpack Compose)
│   ├── app/
│   │   └── src/main/java/com/iams/app/
│   │       ├── IAMSApplication.kt       # @HiltAndroidApp
│   │       ├── MainActivity.kt          # Single-activity host
│   │       ├── di/NetworkModule.kt      # Hilt: Retrofit, OkHttp, ApiService
│   │       ├── data/
│   │       │   ├── api/                 # ApiService, AuthInterceptor, TokenManager, WebSocket
│   │       │   └── model/Models.kt      # Data classes (API DTOs)
│   │       └── ui/
│   │           ├── theme/               # Material 3 monochrome theme
│   │           ├── navigation/          # Routes, NavHost, NavViewModel
│   │           ├── components/          # RtspVideoPlayer, ML Kit processor, overlays, etc.
│   │           ├── auth/                # Login, registration (4 steps), email verification
│   │           ├── student/             # Home, schedule, history, profile
│   │           └── faculty/             # Home, live feed (WebRTC + ML Kit), reports, profile
│   ├── gradle.properties                # IAMS_BACKEND_HOST/PORT (managed by scripts/switch-env.sh)
│   └── build.gradle.kts
│
├── admin/                    # Admin dashboard (React + Vite)
│   ├── src/
│   │   ├── routes/           # Page components (dashboard, users, schedules, analytics, etc.)
│   │   ├── components/       # Shared UI components (data tables, charts, layouts)
│   │   ├── services/         # API service layer
│   │   ├── hooks/            # use-websocket, use-queries, use-page-title
│   │   ├── stores/           # Breadcrumb store
│   │   └── types/            # TypeScript types
│   ├── Dockerfile
│   └── vite.config.ts
│
├── deploy/                   # Production deployment
│   ├── docker-compose.prod.yml   # Backend + Nginx + Redis + mediamtx + Coturn + Certbot
│   ├── nginx.conf                # Reverse proxy config (API, WebSocket, WHEP, admin static)
│   ├── deploy.sh                 # rsync + Docker rebuild script
│   ├── setup-server.sh           # One-time VPS bootstrap
│   └── mediamtx.yml              # mediamtx WebRTC bridge config
│
├── docs/
│   ├── main/                 # Architecture, API reference, database schema, implementation, etc.
│   └── screens/              # Android screen list and navigation flow
│
├── docker-compose.yml        # Local development compose
└── CLAUDE.md                 # Claude Code project instructions
```

---

## System Components

### Backend (FastAPI)

The backend is the brain of the system. It exposes a REST + WebSocket API on port 8000.

**Routers (`/api/v1/...`):**

| Router | Prefix | Purpose |
|--------|--------|---------|
| `auth` | `/auth` | Login, refresh token, email confirmation, password reset |
| `users` | `/users` | CRUD for students, faculty, admins; face registration management |
| `face` | `/face` | Face registration upload, edge device face processing endpoint |
| `rooms` | `/rooms` | Classroom CRUD, room lookup by name |
| `schedules` | `/schedules` | Schedule CRUD, enrollment management |
| `attendance` | `/attendance` | Attendance records, manual entry |
| `presence` | `/presence` | Presence logs, scan results |
| `notifications` | `/notifications` | Notification CRUD, preferences |
| `analytics` | `/analytics` | Attendance rates, engagement scores, anomalies, at-risk |
| `audit` | `/audit` | Audit log entries |
| `edge` | `/edge` | Edge device heartbeat and status monitoring |
| `settings` | `/settings` | System setting key-value store |
| `live_stream` | `/stream` | WebSocket-based camera frame relay (legacy) |
| `hls` | `/hls` | Serve HLS playlists and segments |
| `webrtc` | `/webrtc` | WHEP signaling proxy + ICE config |
| `websocket` | `/ws` | Per-user WebSocket connections for real-time events |

**Background jobs (APScheduler):**

| Job | Schedule | Purpose |
|-----|----------|---------|
| `presence_scan_cycle` | Every 60 s | Run presence tracking for all active sessions |
| `auto_session_manager` | Every 60 s | Auto-start/end sessions based on schedule times |
| `faiss_health_check` | Every 30 min | Compare FAISS vector count vs DB registrations |
| `daily_digest` | 8 PM Manila (Mon–Sat) | Email + in-app daily attendance summary to faculty |
| `weekly_digest` | Mon 8 AM Manila | Email + in-app weekly summary to students |

**Services layer (`backend/app/services/`):**

- `face_service.py` — registration workflow, FAISS index management, reconciliation
- `recognition_service.py` — real-time face recognition from RTSP stream
- `presence_service.py` — scan cycle logic, early-leave detection, score calculation
- `tracking_service.py` — DeepSORT-based track-to-identity mapping
- `analytics_service.py` — attendance rate aggregation and trend analysis
- `anomaly_service.py` — statistical anomaly detection in attendance patterns
- `engagement_service.py` — per-student engagement score computation
- `prediction_service.py` — attendance prediction for at-risk flagging
- `notification_service.py` — WebSocket push + in-app notification creation
- `digest_service.py` — daily/weekly digest generation
- `email_service.py` — Resend API integration
- `auth_service.py` — JWT generation/validation, Supabase GoTrue calls
- `user_service.py` — user CRUD, student record management
- `session_scheduler.py` — auto session start/stop
- `batch_processor.py` — Redis-queue-based batch face recognition
- `ml/insightface_model.py` — InsightFace model singleton (buffalo_l)
- `ml/faiss_manager.py` — FAISS index load/save/rebuild, Redis pub/sub for multi-worker sync

---

### Edge Device (Raspberry Pi)

The edge device runs a continuous camera → detect → send loop. It is entirely stateless regarding identity — it only detects faces and sends cropped JPEG images.

**Camera sources (auto-detected or configured):**
- `picamera2` — Raspberry Pi Camera Module
- `usb` — USB webcam via OpenCV
- `rtsp` — IP camera (e.g., Reolink) via RTSP stream

**Processing pipeline per scan:**
1. Capture frame from camera
2. Run MediaPipe face detection (ShortRange model, 0.6 confidence threshold)
3. Crop each detected face to bounding box
4. Apply CLAHE normalization + dynamic padding
5. Encode as JPEG (quality 85)
6. Smart sampler: skip faces that haven't moved (IoU > 0.3, dedup window 5 s)
7. POST to `POST /api/v1/face/process` as Base64 JSON payload
8. On failure: enqueue to offline queue (max 500, 5-min TTL, retry every 10 s)

**Stream relay:** When `STREAM_RELAY_ENABLED=true`, FFmpeg re-streams the camera RTSP feed to the VPS mediamtx, enabling faculty to view live video via WebRTC from any network.

**Session awareness:** By default, the device polls `GET /api/v1/rooms/{room_id}/session` every 10 seconds. It only scans during an active class session, saving bandwidth and reducing false processing.

**Edge environment variables:**

```env
BACKEND_URL=http://167.71.217.44        # VPS IP or domain
ROOM_ID=<uuid>                          # Or use ROOM_NAME for dynamic resolution
CAMERA_SOURCE=auto                      # auto | picamera | rtsp | usb
RTSP_URL=rtsp://...                     # Required if CAMERA_SOURCE=rtsp
SCAN_INTERVAL=60                        # Seconds between scans
SESSION_AWARE=true
SESSION_POLL_INTERVAL=10
STREAM_RELAY_ENABLED=false
STREAM_RELAY_URL=rtsp://167.71.217.44:8554
USE_SMART_SAMPLER=true
LOG_LEVEL=INFO
```

---

### Android App (Kotlin)

Native Android app built with Kotlin + Jetpack Compose (Material 3). Single `MainActivity` (`@AndroidEntryPoint`) hosts a Navigation Compose graph with separate flows for students and faculty.

**Student flow:** Home dashboard, schedule, attendance history, profile. Self-registration wizard (verify Student ID → create account → email verification → CameraX capture of 3–5 face angles → review + submit).

**Faculty flow:** Home with today's classes, Live Feed screen (the crown jewel — ExoPlayer WebRTC video + on-device ML Kit face detection + backend identity overlay), reports, profile. Faculty accounts are pre-seeded (no self-registration).

**Hybrid detection on the Live Feed screen (gated by `BuildConfig.HYBRID_DETECTION_ENABLED`):**

- **Video delivery** — mediamtx → WebRTC → `SurfaceViewRenderer` on the phone (no backend processing, always smooth).
- **Face detection (positions)** — Google ML Kit runs on-device at ~15 fps against WebRTC frames via `MlKitFrameSink`. Zero network, instant bounding boxes.
- **Face recognition (identities)** — Backend processes RTSP at 5 fps (SCRFD + ByteTrack + ArcFace + FAISS) and broadcasts `{track_id, bbox, name, server_time_ms, frame_sequence}` over WebSocket.
- **Fusion** — `FaceIdentityMatcher` on the phone binds ML Kit detections to backend identities via IoU (greedy assignment with sticky release threshold and identity-hold TTL) so names don't flip when faces cluster.
- **Fallback** — `HybridFallbackController` monitors ML Kit + WebSocket liveness and switches between `HYBRID` / `BACKEND_ONLY` / `DEGRADED` / `OFFLINE` modes automatically.

**Networking:** Retrofit + OkHttp with `AuthInterceptor` for bearer tokens, `TokenManager` persists JWTs in DataStore. `AttendanceWebSocketClient` uses OkHttp's WebSocket with auto-reconnect.

**DI:** Hilt (`IAMSApplication` is `@HiltAndroidApp`, all screens are `@AndroidEntryPoint`). `NetworkModule` provides Retrofit, OkHttp, and the `ApiService`.

**Backend target:** Build-time `BACKEND_HOST` / `BACKEND_PORT` from `android/gradle.properties`, managed exclusively by [scripts/switch-env.sh](scripts/switch-env.sh) — never hand-edited.

---

### Admin Dashboard (React)

A Vite + React SPA served as static files by Nginx at `/admin`. Built with shadcn/ui components and TanStack Query for data fetching.

**Pages:**

| Route | Purpose |
|-------|---------|
| `/dashboard` | System KPIs, recent activity, real-time WebSocket updates |
| `/users/students` | Student list with search, filter, pagination |
| `/users/faculty` | Faculty list |
| `/users/admins` | Admin account management |
| `/users/:id` | User detail with face registrations and attendance history |
| `/schedules` | Schedule list, create/edit schedules |
| `/schedules/:id` | Schedule detail with enrollment management |
| `/attendance` | Attendance records across all sessions |
| `/early-leaves` | Early-leave event log |
| `/face-registrations` | Face registration management |
| `/edge-devices` | Edge device heartbeat and status |
| `/notifications` | System-wide notification log |
| `/audit-logs` | Audit trail for all admin actions |
| `/analytics` | Attendance analytics, anomaly detection, at-risk students |
| `/settings` | System configuration |

---

## Face Recognition Pipeline

### Registration (mobile → backend)

```
Student captures 3–5 face images (different angles)
        ↓
POST /api/v1/face/register  (multipart, Base64 or file)
        ↓
Quality gating per image:
  • Blur check: Laplacian variance > 35 (mobile selfie threshold)
  • Brightness: 40–220 mean pixel intensity
  • Min face size: face area / image area > 5%
  • SCRFD detection score > 0.5
        ↓
Anti-spoofing per image:
  • LBP texture uniformity check
  • FFT high-frequency energy check
        ↓
InsightFace embedding: 512-dim ArcFace vector per image
        ↓
Average embeddings → single representative vector
        ↓
FAISS add() + persist face_embedding DB record
```

### Recognition (edge → backend)

```
Edge device: POST /api/v1/face/process
  { room_id, faces: [{ image_b64, bbox, confidence }], timestamp }
        ↓
Per face:
  Quality gating (CCTV thresholds — stricter blur: Laplacian > 100)
        ↓
  InsightFace embedding extraction
        ↓
  FAISS search(top_k=3):
    cosine_similarity > 0.45  AND  margin(top1 - top2) > 0.10  → match
        ↓
  Anti-spoofing (log-only for CCTV — no blocking)
        ↓
  Attendance / presence log update
        ↓
  WebSocket broadcast to relevant faculty/student
```

### FAISS Index Management

- Type: `IndexFlatIP` (exact inner-product search on normalized vectors = cosine similarity)
- Persisted at `data/faiss/faces.index`
- Loaded into memory at startup; rebuilt on user deletion
- Health check every 30 minutes compares FAISS vector count vs DB active registrations
- Multi-worker sync: index rebuild publishes to Redis channel; all workers reload

---

## Presence Tracking & Early-Leave Detection

Every 60 seconds (configurable via `SCAN_INTERVAL_SECONDS`), the backend's APScheduler triggers a scan cycle:

```
For each active session (room + schedule with ongoing class):
  1. Collect all recognized faces from the last 60 s (from attendance/presence logs)
  2. For each enrolled student:
     → if seen: log present, reset miss counter
     → if not seen: increment consecutive_miss counter
       → if consecutive_miss >= 3: fire EarlyLeaveEvent
          → notify faculty (WebSocket + in-app)
          → notify student (WebSocket + in-app)
          → send email digest if EMAIL_ENABLED
  3. Compute presence_score = (present_scans / total_scans) × 100%
```

**Session lifecycle:**
- Auto-started by `auto_session_manager` job based on schedule start time (with `SESSION_BUFFER_MINUTES=5` buffer)
- Auto-ended at schedule end time + buffer
- Faculty can also manually start/end sessions via the mobile app

**Grace period:** `GRACE_PERIOD_MINUTES=15` — students arriving within 15 minutes of class start are marked present, not late.

---

## Live Video Streaming

Two streaming modes, configurable per deployment:

### WebRTC (primary, <300 ms latency)

```
RPi (RTSP source)
  ↓  FFmpeg stream relay (edge/app/stream_relay.py)
mediamtx container (VPS)  ← RTSP ingest on port 8554
  ↓  WHEP endpoint (HTTP)
Faculty mobile app  ← WebRTC via Coturn TURN relay
```

- mediamtx version: `bluenviron/mediamtx:latest`
- WHEP endpoint proxied through Nginx: `GET /api/v1/webrtc/whep/{path}`
- ICE config served by backend: `GET /api/v1/webrtc/ice-config`
- Coturn TURN server: port 3478, UDP relay ports 49152–49252

### HLS (fallback, ~0.6 s latency)

- FFmpeg transcodes RTSP to 0.2 s segments with forced keyframes
- Playlist: `GET /api/v1/hls/{stream_id}/playlist.m3u8`
- Segments: `GET /api/v1/hls/{stream_id}/{segment}`
- Used when WebRTC is unavailable or explicitly disabled

---

## API Reference

Base URL: `http://167.71.217.44/api/v1` (production) or `http://localhost:8000/api/v1` (dev)

Interactive docs: `GET /api/v1/docs` (Swagger UI) · `GET /api/v1/redoc`

**Authentication:**
All protected endpoints require `Authorization: Bearer <access_token>`.

**Key endpoints:**

```
# Auth
POST   /auth/login                     Login (returns access + refresh tokens)
POST   /auth/refresh                   Refresh access token
POST   /auth/register/student          Student self-registration
GET    /auth/email-confirmed           Email confirmation landing
POST   /auth/forgot-password           Send password reset email
POST   /auth/reset-password            Set new password with OTP

# Face
POST   /face/register                  Register face (3–5 images, multipart)
POST   /face/process                   Edge device face processing (Base64)
DELETE /face/registration/{id}         Remove face registration
GET    /face/status/{user_id}          Face registration status

# Users
GET    /users                          List users (paginated, filterable by role)
POST   /users                          Create user (admin)
GET    /users/{id}                     Get user detail
PUT    /users/{id}                     Update user
DELETE /users/{id}                     Delete user + rebuild FAISS

# Schedules
GET    /schedules                      List schedules
POST   /schedules                      Create schedule
POST   /schedules/{id}/enroll          Enroll student in schedule
DELETE /schedules/{id}/enroll/{uid}    Remove enrollment
POST   /schedules/{id}/session/start   Start session
POST   /schedules/{id}/session/end     End session

# Attendance
GET    /attendance                     List records (filter by student/schedule/date)
POST   /attendance                     Manual attendance entry
GET    /attendance/summary/{user_id}   Attendance summary per student

# Presence
GET    /presence/logs                  Presence log entries
GET    /presence/score/{user_id}       Presence score for a schedule

# Analytics
GET    /analytics/attendance-rate      Overall attendance rates
GET    /analytics/engagement           Engagement scores
GET    /analytics/anomalies            Detected anomalies
GET    /analytics/at-risk              At-risk student list

# WebSocket
WS     /ws/{user_id}                   Real-time event stream
```

---

## Database Schema

Managed by Supabase (PostgreSQL) + Alembic migrations.

**Core tables (20 models):**

| Table | Purpose |
|-------|---------|
| `users` | All users — role: `student` / `faculty` / `admin` |
| `student_records` | Extended student profile (student_id, year, course) |
| `faculty_records` | Extended faculty profile (department, employee_id) |
| `face_registrations` | Links user to a set of face embeddings (status: active/inactive) |
| `face_embeddings` | Individual FAISS embedding vectors (512 floats, stored as blob) |
| `rooms` | Classroom definitions (name, capacity, location) |
| `schedules` | Class schedule (subject, faculty, room, day_of_week, start_time, end_time) |
| `enrollments` | Student–schedule many-to-many |
| `attendance_records` | Per-session check-in record with timestamp and confidence |
| `presence_logs` | Per-60s scan results — present/absent per enrolled student |
| `early_leave_events` | Early-leave detection records with alert status |
| `notifications` | In-app notification messages |
| `notification_preferences` | Per-user notification settings (push, email, types) |
| `system_settings` | Key-value configuration store |
| `audit_logs` | Admin action log (actor, action, target, timestamp) |
| `attendance_anomalies` | ML-detected statistical anomalies |
| `attendance_predictions` | Predicted absence risk scores |
| `engagement_scores` | Per-student engagement metrics |
| `enrollment` | (same as enrollments — see models) |

**Relations:**
- User 1→1 StudentRecord / FacultyRecord
- User 1→N FaceRegistration 1→N FaceEmbedding
- Schedule N→1 Room, N→1 User (faculty)
- Enrollment N→1 User (student), N→1 Schedule
- AttendanceRecord N→1 User, N→1 Schedule
- PresenceLog N→1 Schedule, N→1 User
- EarlyLeaveEvent N→1 AttendanceRecord

---

## Environment Variables

### Backend (`.env`)

```env
# Database
DATABASE_URL=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres

# Supabase (optional — needed only if USE_SUPABASE_AUTH=true)
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<jwt-secret>

# JWT (custom auth — default mode)
SECRET_KEY=<random-256-bit-hex>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis
REDIS_URL=redis://localhost:6379/0

# Face Recognition
RECOGNITION_THRESHOLD=0.45
FAISS_INDEX_PATH=data/faiss/faces.index
INSIGHTFACE_MODEL=buffalo_l

# Presence Tracking
SCAN_INTERVAL_SECONDS=60
EARLY_LEAVE_THRESHOLD=3
GRACE_PERIOD_MINUTES=15

# Email (Resend)
RESEND_API_KEY=re_...
EMAIL_ENABLED=true
RESEND_FROM_EMAIL=IAMS <noreply@iams.jrmsu.edu.ph>

# Streaming
USE_WEBRTC_STREAMING=true
USE_HLS_STREAMING=true
DEFAULT_RTSP_URL=rtsp://...
MEDIAMTX_EXTERNAL=true           # true when running via docker-compose
WEBRTC_TURN_URL=turn:167.71.217.44:3478
WEBRTC_TURN_USERNAME=iams
WEBRTC_TURN_CREDENTIAL=iams-turn-secret-2026

# App
DEBUG=false
CORS_ORIGINS=["https://yourdomain.com"]
```

### Edge Device (`.env`)

```env
BACKEND_URL=http://167.71.217.44
ROOM_ID=<room-uuid>                # Or use ROOM_NAME for auto-resolution
CAMERA_SOURCE=auto                 # auto | picamera | rtsp | usb
RTSP_URL=rtsp://admin:pass@192.168.1.100/stream
SCAN_INTERVAL=60
SESSION_AWARE=true
SESSION_POLL_INTERVAL=10
USE_SMART_SAMPLER=true
STREAM_RELAY_ENABLED=true
STREAM_RELAY_URL=rtsp://167.71.217.44:8554
LOG_LEVEL=INFO
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ and pnpm
- Redis (local or Docker)
- Supabase project (for PostgreSQL)
- CUDA-capable GPU recommended (InsightFace can run on CPU but is slower)

### 1. Clone

```bash
git clone <repository-url>
cd iams
```

### 2. Database setup

- Create a Supabase project at supabase.com
- Copy the connection string (`DATABASE_URL`) from Project Settings → Database
- Optionally run the seed script to populate reference data:
  ```bash
  cd backend && python scripts/seed_school_data.py
  ```

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, REDIS_URL, etc.

# Run Alembic migrations
alembic upgrade head

# Seed admin account
python scripts/seed_data.py

# Start development server
python run.py
# → http://localhost:8000
# → http://localhost:8000/api/v1/docs
```

### 4. Admin dashboard

```bash
cd admin
pnpm install
pnpm dev
# → http://localhost:5173
```

### 5. Android app

```bash
# Point the APK at local Docker or at the VPS (never hand-edit gradle.properties).
./scripts/switch-env.sh local       # LAN IP of this Mac, port 8000
# or: ./scripts/switch-env.sh production   # VPS: 167.71.217.44, port 80

cd android
./gradlew clean installDebug        # Always use `clean` on every environment switch
```

Requires Android Studio (SDK 35, min SDK 26). Open the `android/` folder in Android Studio for iterative development.

### 6. Edge device (Raspberry Pi)

```bash
# On the Raspberry Pi
cd edge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set BACKEND_URL and ROOM_ID (or ROOM_NAME)

python run.py
```

### 7. Running with Docker (local)

```bash
# From project root
docker compose up -d
# Backend: http://localhost:8000
# Redis: localhost:6379
```

---

## Deployment

### Production stack

The production environment runs on a DigitalOcean VPS at `167.71.217.44` managed with Docker Compose.

**Services:**

| Container | Image | Purpose |
|-----------|-------|---------|
| `iams-backend` | Custom Dockerfile | FastAPI + Uvicorn + InsightFace |
| `iams-redis` | redis:7-alpine | Pub/sub + batch queue cache |
| `iams-mediamtx` | bluenviron/mediamtx:latest | RTSP→WHEP WebRTC bridge |
| `iams-coturn` | coturn/coturn:latest | TURN relay for WebRTC NAT traversal |
| `iams-nginx` | nginx:alpine | Reverse proxy, TLS termination, static admin files |
| `iams-certbot` | certbot/certbot | Auto-renew Let's Encrypt certificates |

**Deploy:**

```bash
# From your local machine
bash deploy/deploy.sh
```

The script rsync's the latest code to the VPS and triggers a Docker rebuild.

**First-time VPS setup:**

```bash
# SSH into the VPS
bash deploy/setup-server.sh
```

**Environment file:** `backend/.env.production` — never commit this file.

**Ports:**

| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | TCP | HTTP (redirects to HTTPS) |
| 443 | TCP | HTTPS (Nginx + Certbot) |
| 8554 | TCP | RTSP ingest from edge devices |
| 8887 | UDP | WebRTC media (ICE candidates) |
| 3478 | TCP/UDP | TURN relay (Coturn) |

---

## Hardware Requirements

### Production setup (per classroom)

| Hardware | Spec | Notes |
|----------|------|-------|
| Server / VPS | 2 vCPU, 4 GB RAM minimum | DigitalOcean Droplet (4 GB recommended) |
| Edge device | Raspberry Pi 4 (4 GB) | Runs detection only — no GPU needed |
| Camera | Pi Camera Module 3 or USB webcam | RTSP IP camera also supported |
| Network | Stable WiFi or Ethernet | RPi needs internet access to VPS |
| Student devices | Android phone (SDK 26+) | Students use their own phones. For LOCAL dev mode, device must share the Mac's WiFi subnet. |

### Development machine

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | Any modern x64 | — |
| RAM | 8 GB | 16 GB |
| GPU | None (CPU fallback) | NVIDIA GTX 1650+ (CUDA 11.8) |
| OS | Windows 10 / Ubuntu 20.04 / macOS 12+ | Ubuntu 22.04 |
| Python | 3.11 | 3.11 |
| Node.js | 20 | 20 LTS |

> **Note:** InsightFace (buffalo_l) loads ~320 MB of model weights. On CPU-only machines, recognition latency is ~200–500 ms per face. A GPU reduces this to <30 ms.

---

## Documentation

Full documentation lives in `docs/main/`:

| Document | Description |
|----------|-------------|
| [PRD](docs/main/prd.md) | Product requirements, user flows, pilot testing plan |
| [Architecture](docs/main/architecture.md) | System design decisions, data flow diagrams |
| [Tech Stack](docs/main/tech-stack.md) | Technology choices and rationale |
| [Implementation](docs/main/implementation.md) | How each component works, business rule details |
| [API Reference](docs/main/api-reference.md) | Complete endpoint documentation |
| [Database Schema](docs/main/database-schema.md) | All tables, columns, relationships |
| [Step by Step](docs/main/step-by-step.md) | Development phase guide |
| [Deployment](docs/main/deployment.md) | VPS setup, Docker, Nginx, TLS |
| [Testing](docs/main/testing.md) | Testing strategy, pytest setup |
| [Best Practices](docs/main/best-practices.md) | Coding guidelines |
| [ML Pipeline](docs/main/ml-pipeline-spec.md) | InsightFace + FAISS technical spec |
| [Master Blueprint](docs/main/master-blueprint.md) | Full system blueprint |
| [Screen List](docs/screens/screen-list.md) | Android app screen list and navigation flow |

---

## Team

- **Developer:** CJ Jutba
- **Institution:** Jose Rizal Memorial State University (JRMSU)
- **Context:** Computer Engineering undergraduate thesis

---

## License

Academic use only. Not licensed for commercial deployment without permission.
