# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⛔ Environment Mode (Local / Production)

**Default mode: PRODUCTION (VPS `167.71.217.44`).** Code changes, admin portal (Vercel),
and Android builds all point here unless explicitly switched.

**Switching is done with a single script — never by hand-editing config files.**

```bash
./scripts/switch-env.sh status        # Show current mode
./scripts/switch-env.sh local         # Point Android + admin at local Docker stack
./scripts/switch-env.sh production    # Point Android + admin back at VPS
```

The script edits [android/gradle.properties](android/gradle.properties),
[admin/.env.production](admin/.env.production), and [admin/vite.config.ts](admin/vite.config.ts)
atomically, auto-detects your Mac's LAN IP for local mode (so a physical Android
device on the same WiFi can reach the backend), and preserves unrelated keys
(Supabase VITE_* vars, etc.).

Claude **MUST NOT**:
- Hand-edit [android/gradle.properties](android/gradle.properties), [admin/.env.production](admin/.env.production), [admin/.env](admin/.env), [admin/vite.config.ts](admin/vite.config.ts), or `android/local.properties` to change environment. Always use `./scripts/switch-env.sh`. This guarantees identical results across machines and fresh Claude sessions.
- Run raw `docker compose up`, `docker compose up -d`, `docker compose up --build`, or `docker compose exec ...` directly. Use [scripts/dev-up.sh](scripts/dev-up.sh) (it auto-configures mediamtx with the LAN IP) and [scripts/dev-down.sh](scripts/dev-down.sh).
- Run `./scripts/dev-down.sh` on "switch to production" — leave local Docker running for fast switch-back. Only stop it when the user asks explicitly.

Claude **SHOULD**:
- In PRODUCTION mode: verify against the VPS (`curl http://167.71.217.44/...`, Dozzle at `http://167.71.217.44:9999`, `ssh root@167.71.217.44 'docker logs -f iams-api-gateway'`). Deploy code via `bash deploy/deploy.sh`.
- In LOCAL mode: verify against `http://localhost:8000/...`. Deploy = restart container via `./scripts/dev-up.sh` (it's `docker compose up --build -d`, so idempotent).
- Run local-only, non-container operations freely in either mode: `git`, `./gradlew` (Android), `npm run build`, file edits, tests that don't require the stack.

## Switch Protocol

When the user says **"switch to local"**, Claude runs these steps in order without
further prompting:

1. `./scripts/switch-env.sh status` — report pre-switch mode.
2. `./scripts/switch-env.sh local` — capture output verbatim.
3. `./scripts/dev-up.sh` — foreground, wait for completion. Reports the LAN IP it bound mediamtx to.
4. Check `admin/node_modules`; if missing, `cd admin && npm install`. Then check port 5173 with `lsof -ti :5173`; if nothing is listening, start `cd admin && npm run dev` with `run_in_background: true`. If something is already on 5173, skip (Vite is already up).
5. `cd android && ./gradlew installDebug` — foreground. If this fails with "no connected devices", "ANDROID_HOME not set", or similar environment errors, report the specific failure and tell the user to attach a device or rebuild in Android Studio. Do **NOT** retry; do **NOT** roll back the config switch.
6. `curl -fsS http://localhost:8000/api/v1/health` — verify backend is up.
7. Report: current mode, Docker health, admin dev URL (`http://localhost:5173`), APK install status, API health check.

When the user says **"switch to production"**, Claude runs these steps in order:

1. `./scripts/switch-env.sh status` — report pre-switch mode.
2. `./scripts/switch-env.sh production` — capture output.
3. `curl -fsS http://167.71.217.44/api/v1/health` — verify VPS is up.
4. Report: current mode, VPS health, admin URL (`https://iams-thesis.vercel.app`), reminder to rebuild the APK if the user needs the new build on device.
5. Do **NOT** run `./scripts/dev-down.sh`. Leave local Docker running for a fast switch-back; the user can stop it manually (`./scripts/dev-down.sh`) when they want a clean slate.
6. Do **NOT** run `bash deploy/deploy.sh`. "Switch to production" points clients at the VPS; it does not deploy code changes. Deploying is a separate, explicit "deploy" or "push to production" command.

Half-switched states are valid. If step 5 of "switch to local" fails (no Android
device attached), configs are already flipped and Docker is already up — the user
can attach a device later and re-run `./gradlew installDebug`. Do NOT roll back
on partial failure.

## Project Overview

IAMS (Intelligent Attendance Monitoring System) is a CCTV-based facial recognition attendance system for JRMSU. It features:
- Raspberry Pi edge device as a dumb RTSP relay (FFmpeg, no ML)
- mediamtx for RTSP ingestion and WebRTC serving
- FastAPI backend for face recognition (InsightFace ArcFace + FAISS) and attendance tracking
- Kotlin Android app with ExoPlayer (video), ML Kit (on-device face detection), CameraX (face registration)
- PostgreSQL database (runs on VPS via Docker)
- React + Vite admin portal (served from Vercel, talks to VPS API)

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
       ├──> WebRTC ──> Kotlin App
       │                 ├── SurfaceViewRenderer (smooth video)
       │                 └── MlKitFrameSink (~15fps face detection, emits MlKitFace)
       │                           │
       │                           v
       │                 FaceIdentityMatcher (IoU-binds ML Kit faces to backend identities)
       │                           │
       │                           v
       │                 HybridTrackOverlay (draws boxes at ML Kit cadence, labels from backend)
       │
       └──> Backend FrameGrabber (grabs frames at 5fps production)
                 │
                 v
            SCRFD + ByteTrack + ArcFace → FAISS match → DB
                 │
                 v
            WebSocket broadcast {track_id, bbox, name, server_time_ms, frame_sequence}
                 │
                 └──> merged by FaceIdentityMatcher on the phone
```

**Three independent systems (hybrid — master-plan 2026-04-17):**
1. **Video delivery** — mediamtx → WebRTC → phone (always smooth, no backend processing).
2. **Face detection (position)** — ML Kit on phone, consuming WebRTC frames via `MlKitFrameSink`. ~15fps, zero network.
3. **Face recognition (identity)** — Backend at 5fps (production): SCRFD + ByteTrack + ArcFace + FAISS → WebSocket → `FaceIdentityMatcher` on phone sticks names to ML Kit faces via IoU.

The hybrid overlay is gated by `BuildConfig.HYBRID_DETECTION_ENABLED` (default on). When false, the app falls back to the legacy backend-authoritative `InterpolatedTrackOverlay`. `HybridFallbackController` automatically drops to the legacy path if the ML Kit sink stalls or to no-overlay if both legs go silent.

## Development Workflow

In **PRODUCTION mode** (default), code runs on the VPS. Claude's local role is to
edit, commit, and deploy. In **LOCAL mode**, the full stack runs on this Mac via
Docker Desktop, reached at the LAN IP for physical devices.

Swap modes with `./scripts/switch-env.sh {local|production}` — see the "Switch
Protocol" section above for the full recipe.

### Deploy code changes to VPS
```bash
bash deploy/deploy.sh
```
This rsyncs the repo, rebuilds the VPS containers, and restarts the stack. This is the ONLY way Claude should bring up containers.

### Inspect the VPS stack

From this Mac:
```bash
curl http://167.71.217.44/api/v1/health         # liveness
curl http://167.71.217.44/api/v1/health/time    # epoch ms
curl http://167.71.217.44/api/v1/docs           # swagger HTML
```

Live logs (browser): `http://167.71.217.44:9999` (Dozzle).

SSH into the VPS for anything deeper:
```bash
ssh root@167.71.217.44 'docker ps'
ssh root@167.71.217.44 'docker logs --tail 200 iams-api-gateway'
ssh root@167.71.217.44 'docker exec iams-postgres psql -U iams -d iams -c "SELECT count(*) FROM users;"'
```

### Database Reset & Seed (VPS)

When the user asks to "seed the data" or "reset the database":
```bash
ssh root@167.71.217.44 'docker exec iams-api-gateway python -m scripts.seed_data'
```

This wipes ALL data on the VPS and reseeds from scratch: ~180 student records, 5 faculty accounts
(`faculty.eb226@gmail.com`, `faculty.eb227@gmail.com`, plus 3 real JRMSU instructors;
all password `password123`), admin (`admin@admin.com` / `123`), rooms, schedules,
and system settings.

**Test schedules — REMOVE BEFORE FINAL PRODUCTION CUT.** The seed script generates one
synthetic schedule set used only for thesis demo / development:

- `EB226-HHMM` / `EB227-HHMM` — 672 rolling 30-min sessions total
  (48 slots/day × 7 days × 2 rooms) with a per-schedule
  `early_leave_timeout_minutes=2`. Exercises the full
  PRESENT / LATE / ABSENT / EARLY_LEAVE state machine on both rooms any time
  of day.

For the final production cut, delete `_seed_rolling_sessions()` and the `ROLLING_ROOMS`
list from [`backend/scripts/seed_data.py`](backend/scripts/seed_data.py).
The real schedules are the 15 entries already in `SCHEDULE_DEFS` (Elumba /
Gahisan / Lasco), sourced from
[`docs/data/ListofStudents_All-Thesis-purposes-updated1.md`](docs/data/ListofStudents_All-Thesis-purposes-updated1.md).

### Testing
Unit tests that don't need a live stack can run against a read of the code. If a
test requires the stack:
- **LOCAL mode:** `docker exec iams-api-gateway python -m pytest tests/ -q -k faiss`.
- **PRODUCTION mode:** `ssh root@167.71.217.44 'docker exec iams-api-gateway python -m pytest tests/ -q -k faiss'`.

### Kotlin Android App (builds locally, targets whichever mode is active)
```bash
cd android
./gradlew assembleDebug        # Build debug APK
./gradlew installDebug         # Install on connected device/emulator
```
Open in Android Studio for development. Requires Android SDK 35, min SDK 26.
The committed `android/gradle.properties` points at whichever environment was last
set by `./scripts/switch-env.sh`. For LOCAL mode, the script writes the Mac's LAN
IP so a physical device on the same WiFi can reach the backend.

### Admin Portal
```bash
cd admin
npm install
npm run dev                    # LOCAL mode: dev server at http://localhost:5173, proxies to local Docker
npm run build                  # PRODUCTION mode: static build for Vercel deploy
```
Vercel deploys `admin/.env.production` automatically. In LOCAL mode, use `npm run dev`
and let Vite's proxy (now pointed at `http://localhost:8000`) handle API calls —
don't try to serve the Vercel build from localhost because HTTPS→HTTP mixed content
will break. In PRODUCTION mode, the Vercel-hosted admin is the source of truth.

### Edge Device (Raspberry Pi, separate deploy)
```bash
cd edge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py
```
The RPi only runs an FFmpeg relay — no ML, no face detection. Deployed to the physical RPi, not this Mac.

## First-time Setup (fresh clone on a new Mac)

A fresh `git clone` does NOT include `.env` files (they're gitignored). Minimum
needed locally:

```bash
# Admin (required for npm run build AND for switch-env.sh to rewrite)
[ -f admin/.env.production ] || cp admin/.env.production.example admin/.env.production

# Backend (only if you plan to run LOCAL mode)
[ -f backend/.env ] || cp backend/.env.example backend/.env
```

`android/local.properties` is created automatically the first time you open the
project in Android Studio (for `sdk.dir`). Do NOT add `IAMS_BACKEND_HOST=...`
overrides — `./scripts/switch-env.sh` manages `android/gradle.properties` directly,
and `local.properties` entries would silently override it.

Default mode after a fresh clone is whatever is committed on `feat/cloud-based`
(PRODUCTION → VPS). Run `./scripts/switch-env.sh status` to confirm, then
`./scripts/switch-env.sh local` if you want the local stack.

## Canonical Production Config

`feat/cloud-based` is the production branch. The committed values of the files below
are always the PRODUCTION snapshot. `./scripts/switch-env.sh local` mutates them
in-place; `./scripts/switch-env.sh production` restores them. **Never commit a
local-mutated version of these files.**

| File | Committed? | Purpose |
|------|-----------|---------|
| `android/gradle.properties` | ✅ yes | Android build config — PRODUCTION values committed, mutated by switch-env |
| `android/local.properties` | ❌ gitignored | Per-machine — sdk.dir only; MUST NOT contain IAMS_* overrides |
| `admin/.env.production` | ✅ yes | Admin build config — PRODUCTION values committed, mutated by switch-env (Supabase keys preserved across switches) |
| `admin/vite.config.ts` | ✅ yes | Vite dev proxy — PRODUCTION target committed, mutated by switch-env |
| `backend/.env.production` | ✅ yes | Backend VPS environment (used by `deploy.sh`) — NOT toggled |
| `backend/.env` | ❌ gitignored | Backend LOCAL Docker environment — NOT toggled (stays local-tuned) |

### Expected PRODUCTION values (committed snapshot)

`android/gradle.properties`:
```properties
IAMS_BACKEND_HOST=167.71.217.44
IAMS_BACKEND_PORT=80
IAMS_MEDIAMTX_PORT=8554
IAMS_MEDIAMTX_WEBRTC_PORT=8889
```

`admin/.env.production`:
```env
VITE_API_URL=/api/v1
VITE_WS_URL=ws://167.71.217.44
# (Supabase keys below — preserved across switch-env runs)
```

`admin/vite.config.ts` (proxy targets):
```ts
'/api/v1/ws': { target: 'ws://167.71.217.44', ws: true, changeOrigin: true }
'/api':       { target: 'http://167.71.217.44', changeOrigin: true }
```

### Expected LOCAL values (after `./scripts/switch-env.sh local`)

Same files, but with host → auto-detected Mac LAN IP, port → `8000`, Vite proxies
→ `http://localhost:8000` / `ws://localhost:8000`. Run `./scripts/switch-env.sh status`
any time to confirm current mode.

**Invariant:** When committing, always run `./scripts/switch-env.sh production`
first to ensure the committed snapshot is PRODUCTION.

## Deploy Protocol (VPS)

**Trigger phrase:** "deploy" or "push to production" → run the steps below top to bottom. If a step fails, stop and report — do not guess.

**Step 1 — Confirm no stray Android override.**
Read `android/local.properties`. If it contains any `IAMS_BACKEND_HOST=`, `IAMS_BACKEND_PORT=`, `IAMS_MEDIAMTX_PORT=`, or `IAMS_MEDIAMTX_WEBRTC_PORT=` lines, remove or comment them out so `gradle.properties` wins.

**Step 2 — Confirm `android/gradle.properties` has production values** (above).

**Step 3 — Confirm `admin/.env.production` has production URLs** (above).

**Step 4 — Deploy.**
```bash
bash deploy/deploy.sh
```
Wait for it to finish. Do NOT Ctrl-C.

Prerequisite: SSH access to `root@167.71.217.44`. If you see `Permission denied (publickey)` or `Host key verification failed`, stop and ask the user — do NOT try to work around it.

**Step 5 — Verify.**
```bash
curl http://167.71.217.44/api/v1/health             # expect 200
curl http://167.71.217.44/api/v1/health/time        # expect epoch ms
curl http://167.71.217.44/api/v1/docs               # expect swagger HTML
```

**Step 6 — Verify Room `camera_endpoint` on VPS (only after a reseed).**
On the VPS, endpoints must be `rtsp://mediamtx:8554/<streamKey>`:
```bash
TOKEN=$(curl -s -X POST http://167.71.217.44/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin@admin.com","password":"123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s http://167.71.217.44/api/v1/rooms/ -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
If any endpoint is wrong, PATCH it:
```bash
curl -X PATCH http://167.71.217.44/api/v1/rooms/<UUID> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"camera_endpoint":"rtsp://mediamtx:8554/<streamKey>"}'
```

**Step 7 — Report to user.**
- `deploy.sh` succeeded / failed
- Health endpoints OK
- "Rebuild the Android APK in Android Studio and install on any device that needs the new build."
- Logs dashboard: `http://167.71.217.44:9999`.

## Key Technical Details

### Face Recognition Pipeline
- **Registration:** CameraX captures 3-5 face angles on phone → upload to backend → SCRFD detect → ArcFace embed → store in FAISS
- **Recognition:** Backend grabs frame → SCRFD detect → ArcFace embed → FAISS search → match if cosine similarity > threshold
- **Model:** InsightFace buffalo_l (SCRFD detection + ArcFace recognition), 512-dim embeddings

### On-Device Face Detection (ML Kit)
- Google ML Kit Face Detection runs on the Android phone at ~15 fps (every 2nd WebRTC frame).
- Processes frames from `MlKitFrameSink` (a WebRTC `VideoSink`), not ExoPlayer's TextureView.
- Draws real-time bounding boxes (no network round-trip).
- `FaceIdentityMatcher` binds ML Kit faces to backend-recognised identities via IoU. The backend is the single source of truth for names; ML Kit is the single source of truth for positions. See `docs/plans/2026-04-17-hybrid-detection/`.

### Hybrid Detection (gated by BuildConfig.HYBRID_DETECTION_ENABLED)
- **ML Kit (phone):** ~15 fps detection, instant local bounding boxes.
- **Backend (5 fps production):** SCRFD + ByteTrack + ArcFace + FAISS; broadcasts `{track_id, bbox, name, server_time_ms, frame_sequence}` over WebSocket.
- **Matcher (phone):** greedy IoU assignment with sticky release threshold and identity-hold TTL; swap-prevention logic stops name-flipping when two faces cluster.
- **Fallback:** `HybridFallbackController` monitors ML Kit + WebSocket liveness. Modes: `HYBRID` / `BACKEND_ONLY` / `DEGRADED` / `OFFLINE`. The screen picks the right overlay per mode automatically.
- **Diagnostic HUD:** long-press the video area in debug builds to toggle a live FPS/skew/binding-count overlay.
- **Tuning values:** see `docs/plans/2026-04-17-hybrid-detection/TUNING.md`.

### Continuous Presence Tracking
- Backend runs real-time pipeline at 5fps during active sessions on VPS (see `backend/.env.production::PROCESSING_FPS`).
- Configurable early-leave timeout per schedule (default from settings).
- Presence score = (total_present / total_scans) × 100%.

### FAISS Index
- `IndexFlatIP` with 512-dim ArcFace embeddings
- Cosine similarity via inner product on L2-normalized vectors
- Persisted to `data/faiss/faces.index` inside the `iams-api-gateway` container on the VPS.

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
│   ├── realtime_tracker.py      # ByteTrack + cached ArcFace recognition
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
├── .env.production        # VITE_API_URL, VITE_WS_URL (points at VPS)
└── vite.config.ts
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

- Base URL: `http://167.71.217.44/api/v1`
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

## VPS Infrastructure (DigitalOcean)

**IP:** `167.71.217.44` — all services run here.

### Production stack (Docker Compose — on VPS only)
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

## Plan Mode: Lesson Capture

Every plan must end with a `## Lessons` section containing insights discovered during planning — things like "never do X", "Y breaks because Z", or "always check W first". These are written in the plan file during planning.

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
