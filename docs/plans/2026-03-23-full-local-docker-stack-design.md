# Full Local Docker Stack — Design Document

**Date:** 2026-03-23
**Goal:** Move the entire IAMS system to a fully self-contained Docker stack (no Supabase dependency), with near real-time face recognition, and deploy the same stack to DigitalOcean VPS (4 vCPU / 8GB RAM, $48/mo).

---

## 1. Infrastructure — Docker Services

### Local Development (7 services)

| Service | Image | Port | Purpose |
|---|---|---|---|
| **postgres** | `postgres:16-alpine` | 5432 | All application data |
| **redis** | `redis:7-alpine` | 6379 | Identity cache, pub/sub, tracker state |
| **mediamtx** | `bluenviron/mediamtx:latest` | 8554, 8887, 8889 | RTSP ingest + WebRTC relay |
| **coturn** | `coturn/coturn:latest` | 3478 | TURN relay for WebRTC NAT traversal |
| **api-gateway** | Custom Dockerfile (FastAPI) | 8000 | Backend + ML pipeline (direct access) |
| **dozzle** | `amir20/dozzle:latest` | 9999 | Real-time log viewer UI |
| **adminer** | `adminer:latest` | 8080 | Database viewer UI |

### Production (7 services)

| Service | Image | Port | Purpose |
|---|---|---|---|
| **postgres** | `postgres:16-alpine` | 5432 (internal) | All application data |
| **redis** | `redis:7-alpine` | 6379 (internal) | Identity cache, pub/sub, tracker state |
| **mediamtx** | `bluenviron/mediamtx:latest` | 8554, 8887, 8889 | RTSP ingest + WebRTC relay |
| **coturn** | `coturn/coturn:latest` | 3478 | TURN relay |
| **api-gateway** | Custom Dockerfile (FastAPI) | 8000 (internal) | Backend + ML pipeline |
| **nginx** | `nginx:alpine` | 80, 443 | SSL + reverse proxy + rate limiting |
| **dozzle** | `amir20/dozzle:latest` | 9999 | Log viewer |

**Key differences:** Production adds nginx (SSL, rate limiting), removes Adminer (security risk). No direct access to api-gateway or postgres from outside.

### Docker Compose Configuration

```yaml
# PostgreSQL with seed data
postgres:
  image: postgres:16-alpine
  ports:
    - "5432:5432"
  environment:
    POSTGRES_DB: iams
    POSTGRES_USER: iams
    POSTGRES_PASSWORD: iams_dev_password
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./backend/db/init.sql:/docker-entrypoint-initdb.d/01-init.sql
    - ./backend/db/seed.sql:/docker-entrypoint-initdb.d/02-seed.sql

# Redis — cache only, no persistence
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru --save ""

# coturn — TURN server for WebRTC NAT traversal
coturn:
  image: coturn/coturn:latest
  ports:
    - "3478:3478"
    - "3478:3478/udp"
  command: >
    -n --log-file=stdout
    --realm=iams
    --fingerprint
    --lt-cred-mech
    --user=iams:iams-turn-secret
    --no-tls --no-dtls

# Dozzle — log viewer
dozzle:
  image: amir20/dozzle:latest
  ports:
    - "9999:8080"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro

# Adminer — DB viewer (dev only)
adminer:
  image: adminer:latest
  ports:
    - "8080:8080"
```

### Clean Reset

To wipe all data and reseed:
```bash
docker compose down -v   # -v removes volumes (wipes DB)
docker compose up -d     # init.sql + seed.sql run on fresh DB
```

---

## 2. Real-Time Pipeline Architecture

**Strategy:** Detect every frame, track always, recognize only NEW faces (ByteTrack + ArcFace).

```
FrameGrabber (RTSP → FFmpeg subprocess → numpy frames at PROCESSING_FPS)
       │
       ▼
   SCRFD Detection (~30-50ms on 4vCPU)
       │  face bboxes + embeddings
       ▼
   ByteTrack (~2ms)
       │  persistent track IDs across frames
       ▼
   Identity Cache (in-memory dict)
       │
       ├─ NEW track? → ArcFace + FAISS search (~20-30ms) → cache name
       ├─ KNOWN track? → reuse cached name (0ms)
       └─ RE-VERIFY interval elapsed? → re-run ArcFace to confirm
       │
       ▼
   TrackPresenceService
       │  check-in events, early-leave detection (3 consecutive misses)
       ▼
   WebSocket broadcast (frame_update at 10fps) → Android app
```

### Timing Budget (10fps = 100ms per frame)

| Step | Local (Apple Silicon) | VPS (4 vCPU) |
|---|---|---|
| SCRFD detect | ~10ms | ~30-50ms |
| ByteTrack | ~2ms | ~2ms |
| ArcFace + FAISS (new face only) | ~8ms | ~20-30ms |
| **Total (new face)** | **~20ms** | **~80ms** |
| **Total (tracked face)** | **~12ms** | **~50ms** |

### Android App Real-Time Experience

1. **ML Kit** (on-device) — draws bounding boxes at 30fps, no network needed
2. **Backend** — sends `frame_update` via WebSocket at 10fps with track IDs + names
3. **App** — matches backend names to ML Kit boxes via IoU → names appear within ~100-200ms

### Key Config Settings

| Setting | Value | Purpose |
|---|---|---|
| `PROCESSING_FPS` | 10.0 | Backend frame processing rate |
| `WS_BROADCAST_FPS` | 10.0 | WebSocket update rate |
| `REVERIFY_INTERVAL` | configurable | Seconds before re-checking a tracked identity |
| `TRACK_LOST_TIMEOUT` | configurable | Seconds before expiring a lost track |
| `RECOGNITION_THRESHOLD` | 0.30 (dev) / 0.45 (prod) | Min cosine similarity for match |

### Existing Implementation (no changes needed)

- `realtime_tracker.py` — ByteTrack + identity cache
- `realtime_pipeline.py` — SessionPipeline async loop
- `attendance_engine.py` — stateless scan engine (fallback)
- `frame_grabber.py` — RTSP frame source

---

## 3. Auth System (Replacing Supabase Auth)

### Overview

Self-contained JWT auth using python-jose + bcrypt. No external auth provider.

### Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/auth/register` | POST | Student self-registration |
| `/api/v1/auth/login` | POST | Login (student + faculty) |
| `/api/v1/auth/refresh` | POST | Refresh token rotation |
| `/api/v1/auth/me` | GET | Get current user profile |

### Registration Flow

```
POST /api/v1/auth/register
  Body: { student_id, first_name, last_name, email, password }
  → Validate student_id + email uniqueness
  → bcrypt hash password (12 rounds)
  → Insert into users table (role: student, status: active)
  → Issue JWT access token (30min) + refresh token (7 days)
  → Return { access_token, refresh_token, user }
```

### Login Flow

```
POST /api/v1/auth/login
  Body: { email, password }
  → Lookup user by email
  → bcrypt verify password
  → Issue JWT access token (30min) + refresh token (7 days)
  → Return { access_token, refresh_token, user }
```

### Token Refresh Flow

```
POST /api/v1/auth/refresh
  Body: { refresh_token }
  → Validate refresh token (not expired, not revoked)
  → Issue new access + refresh token pair
  → Revoke old refresh token (rotation prevents replay)
  → Return { access_token, refresh_token }
```

### JWT Payload

```json
{
  "sub": "user_uuid",
  "role": "student|faculty|admin",
  "exp": 1711234567,
  "iat": 1711232767,
  "type": "access|refresh"
}
```

### What Changes in Codebase

| File | Change |
|---|---|
| `auth_service.py` | Rewrite: bcrypt + python-jose instead of Supabase SDK |
| `users` model | Add `password_hash` column |
| `config.py` | Remove all `SUPABASE_*` vars, keep `JWT_SECRET_KEY` |
| `dependencies.py` | Update `get_current_user` to decode local JWT |
| Android `TokenManager.kt` | Add `refresh_token` storage |
| Android `AuthInterceptor.kt` | Add 401 → refresh → retry logic |
| Android `Models.kt` | Update `LoginResponse` to include `refresh_token` |
| Android auth screens | Remove email verification flow |

### What Stays the Same

- Android `Authorization: Bearer <token>` header — unchanged
- FastAPI dependency injection pattern — unchanged
- Role-based access control — unchanged

---

## 4. Database Schema & Migration

### Strategy

Fresh PostgreSQL in Docker. `init.sql` creates schema, `seed.sql` populates test data. `docker compose down -v && docker compose up -d` gives a clean slate.

### Schema Changes from Current

| Change | Details |
|---|---|
| Add `password_hash` to `users` | `TEXT NOT NULL`, stores bcrypt hash |
| Add `refresh_tokens` table | Track issued refresh tokens for rotation/revocation |
| Remove Supabase auth UID refs | `users.id` is our own UUID, no external auth UID |

### Tables

```sql
-- Core user table
users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id VARCHAR(20) UNIQUE,  -- NULL for faculty
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'student',  -- student|faculty|admin
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
)

-- Refresh token tracking
refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,  -- bcrypt hash of refresh token
  expires_at TIMESTAMPTZ NOT NULL,
  revoked BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Existing tables (unchanged)
face_registrations (id, user_id, faiss_id, is_active, created_at)
face_embeddings (id, user_id, embedding_vector, angle_label, created_at)
rooms (id, name, building, rtsp_url, is_active, created_at)
schedules (id, subject_name, subject_code, faculty_id, room_id, day_of_week, start_time, end_time, semester, academic_year, is_active)
enrollments (id, student_id, schedule_id, enrolled_at)
attendance_records (id, user_id, schedule_id, check_in_time, status, presence_score, created_at)
presence_logs (id, schedule_id, user_id, scan_time, is_present, track_id)
early_leave_events (id, schedule_id, user_id, leave_time, consecutive_misses, notified)
```

### Seed Data

```sql
-- Faculty accounts (pre-seeded, bcrypt hashed passwords)
INSERT INTO users (id, email, password_hash, first_name, last_name, role) VALUES
  ('faculty-uuid-1', 'faculty1@jrmsu.edu.ph', '$2b$12$...', 'Juan', 'Dela Cruz', 'faculty'),
  ('faculty-uuid-2', 'faculty2@jrmsu.edu.ph', '$2b$12$...', 'Maria', 'Santos', 'faculty');

-- Rooms
INSERT INTO rooms (id, name, building, rtsp_url) VALUES
  ('room-uuid-1', 'Room 101', 'Main Building', 'rtsp://mediamtx:8554/room101/raw');

-- Schedules
INSERT INTO schedules (...) VALUES (...);

-- Test students (optional, for development)
INSERT INTO users (...) VALUES (...);
INSERT INTO enrollments (...) VALUES (...);
```

---

## 5. Android App Changes

### Unchanged (vast majority)

- ExoPlayer + WebRTC live feed pipeline
- ML Kit face detection (30fps on-device)
- FaceOverlay IoU name matching with backend tracks
- CameraX face registration capture
- WebSocket client (OkHttp)
- Navigation, Material 3 theme, Hilt DI
- All student/faculty screens (except auth)

### Changes Required

| File | Change | Effort |
|---|---|---|
| `ApiService.kt` | Update auth endpoints to match new paths | Small |
| `TokenManager.kt` | Add `refresh_token` storage in DataStore | Small |
| `AuthInterceptor.kt` | Add 401 → call `/auth/refresh` → retry original request | Medium |
| `Models.kt` | Add `refresh_token` to `LoginResponse` | Small |
| `RegisterStep1Screen.kt` | Remove email verification step reference | Small |
| `EmailVerificationScreen.kt` | Remove or disable (skipped for now) | Small |
| `RegistrationViewModel.kt` | Update to call new register endpoint format | Small |
| `build.gradle.kts` | No change (BACKEND_HOST already configurable) | None |

### Auth Interceptor Token Refresh Logic

```kotlin
// In AuthInterceptor.kt
if (response.code == 401 && !request.url.encodedPath.contains("/auth/")) {
    val newTokens = refreshTokens()  // POST /api/v1/auth/refresh
    if (newTokens != null) {
        tokenManager.saveTokens(newTokens)
        // Retry original request with new access token
        val retryRequest = request.newBuilder()
            .header("Authorization", "Bearer ${newTokens.accessToken}")
            .build()
        return chain.proceed(retryRequest)
    } else {
        // Refresh failed — force logout
        tokenManager.clear()
    }
}
```

---

## 6. WebSocket Protocol (No Changes)

### Channels

| Endpoint | Purpose | Rate |
|---|---|---|
| `/api/v1/ws/attendance/{schedule_id}` | Live tracking for a session | ~10fps |
| `/api/v1/ws/alerts/{user_id}` | Early-leave alerts | Event-driven |

### Message Types (backend → app)

```json
// frame_update — every frame (~10fps)
{
  "type": "frame_update",
  "timestamp": 1711234567.89,
  "tracks": [
    {"track_id": 1, "bbox": [0.15, 0.20, 0.35, 0.60], "name": "Juan Dela Cruz", "confidence": 0.92, "user_id": "uuid", "status": "recognized"}
  ],
  "fps": 9.8,
  "processing_ms": 45.2
}

// attendance_summary — every 5 seconds
{
  "type": "attendance_summary",
  "present_count": 15,
  "total_enrolled": 30,
  "absent": ["Maria Torres", "Pedro Garcia"]
}

// check_in — event-driven
{"type": "check_in", "user_id": "uuid", "name": "Juan Dela Cruz", "timestamp": "..."}

// early_leave — event-driven
{"type": "early_leave", "user_id": "uuid", "name": "Juan Dela Cruz", "missed_count": 3}

// early_leave_return — event-driven
{"type": "early_leave_return", "user_id": "uuid", "name": "Juan Dela Cruz"}
```

---

## 7. Face Registration Flow (Minor Changes)

### Flow (unchanged)

```
CameraX (3-5 angles) → base64 upload → POST /api/v1/face/register
  → SCRFD detect face per image
  → ArcFace generate 512-dim embedding per image
  → Average + L2 normalize embeddings
  → Add to FAISS IndexFlatIP
  → Save face_registration + face_embeddings to PostgreSQL
  → Persist FAISS index to data/faiss/faces.index
```

### What Changes

| Before | After |
|---|---|
| Auth verified via Supabase JWT | Auth verified via local JWT |
| DB writes to Supabase Cloud PostgreSQL | DB writes to local Docker PostgreSQL |
| Images could hit Supabase Storage | Images stored in Docker volume (`/app/data/uploads/`) |

---

## 8. Environment Variables

### Local Development (.env)

```env
# Database
DATABASE_URL=postgresql://iams:iams_dev_password@postgres:5432/iams

# Auth
JWT_SECRET_KEY=dev-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis
REDIS_URL=redis://redis:6379/0

# ML
RECOGNITION_THRESHOLD=0.30
PROCESSING_FPS=10.0
WS_BROADCAST_FPS=10.0
RECOGNITION_FPS=15.0

# Streaming
CAMERA_SOURCE=mediamtx
USE_WEBRTC_STREAMING=true
MEDIAMTX_EXTERNAL=false

# Debug
DEBUG=true
```

### Production (.env.production)

```env
# Database
DATABASE_URL=postgresql://iams:STRONG_PASSWORD_HERE@postgres:5432/iams

# Auth
JWT_SECRET_KEY=STRONG_SECRET_HERE

# Redis
REDIS_URL=redis://redis:6379/0

# ML
RECOGNITION_THRESHOLD=0.45
USE_GPU=false

# Debug
DEBUG=false
```

**Removed:** All `SUPABASE_*`, `USE_SUPABASE_AUTH`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`.

---

## Lessons

- Supabase Cloud adds 50-150ms latency per DB query — unacceptable for a real-time system doing 10 frames/sec. Local PostgreSQL is mandatory for this use case.
- ByteTrack + cached ArcFace is the proven pattern for "real-time" recognition on CPU — recognize once, track continuously, re-verify periodically. True per-frame ArcFace is not feasible on 4 vCPU.
- coturn is essential for WebRTC reliability — without TURN, school/corporate WiFi with restrictive NAT will produce black screens on the live feed.
- Email verification is a nice-to-have, not a thesis requirement — skip it to reduce scope and add later if needed.
- The Android app barely changes because it already uses standard JWT + Retrofit patterns — the auth provider is transparent to the client.
