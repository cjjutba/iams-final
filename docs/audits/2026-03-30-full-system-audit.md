# IAMS Full System Audit Report

**Date:** 2026-03-30
**Branch:** `feat/architecture-redesign`
**Audited by:** 7 specialized agents (Backend Core, Business Logic, Android App, Auth/Security, Database, WebSocket, DevOps)

---

## Executive Summary

**Total issues found: ~170** across all layers of the system.

| Severity | Count | Key Themes |
|----------|-------|------------|
| **CRITICAL** | 18 | Unauthenticated endpoints, secrets in git, hardcoded credentials, missing model files, app crashes |
| **HIGH** | 33 | No HTTPS, no rate limiting on login, privilege escalation, FAISS thread safety, event loop blocking, memory leaks |
| **MEDIUM** | 47 | N+1 queries, race conditions, missing cascades, stale state, poor error handling |
| **LOW** | ~35 | Code duplication, deprecated APIs, missing constraints, logging concerns |

### Top 10 Issues to Fix Immediately

1. **WebSocket endpoints have ZERO authentication** — anyone can subscribe to any class's attendance data or any user's alerts
2. **Edge API (`/face/process`, `/face/gone`) has no auth** — EDGE_API_KEY exists in config but is never checked
3. **Camera credentials + JWT secret committed to git** — camera RTSP passwords in mediamtx configs, same JWT secret in dev and prod
4. **No HTTPS in production** — JWTs, face images, passwords traverse the network in cleartext
5. **No rate limiting on login endpoint** — brute-force password attacks are trivial
6. **Backend Dockerfile runs as root** — container compromise gives root access
7. **CORS wildcard `["*"]` in production** — defeats same-origin protections
8. **FAISS index has no thread safety** — concurrent reads/writes cause data races
9. **Confidence field mismatch** (`"similarity"` vs `"confidence"`) — all presence logs store `NULL` confidence
10. **Android registration crashes** — navigation `getBackStackEntry` during exit animation (FIXED in this session)

---

## 1. SECURITY (29 findings)

### Critical

| # | Issue | File | Impact |
|---|-------|------|--------|
| S-C1 | WebSocket endpoints have no JWT authentication | `routers/websocket.py:160-181` | Anyone can view real-time attendance for any class |
| S-C2 | JWT SECRET_KEY has weak default fallback | `config.py:26` | Attacker can forge tokens if env var is unset |
| S-C3 | Edge API endpoints completely unauthenticated | `routers/face.py` (process/gone/recognize) | Fake face data injection into attendance |
| S-C4 | CORS wildcard `["*"]` with `allow_credentials=True` | `config.py:36` | Cross-origin credential theft |
| S-C5 | Camera RTSP credentials committed to git | `deploy/mediamtx.dev.yml:60-80` | Camera access by anyone with repo access |

### High

| # | Issue | File |
|---|-------|------|
| S-H1 | No rate limiting on login, register, refresh, change-password | `routers/auth.py` |
| S-H2 | RefreshToken model exists but is completely unused — no rotation, no revocation | `utils/security.py` |
| S-H3 | Faculty can update ANY user's profile and deregister ANY face | `routers/users.py`, `routers/face.py` |
| S-H4 | Same JWT SECRET_KEY in dev and prod .env files | `.env` / `.env.production` |
| S-H5 | No content-type / magic-byte validation on face uploads | `routers/face.py` |
| S-H6 | JWT error messages leak internal details | `utils/dependencies.py` |
| S-H7 | No failed login lockout mechanism | `services/auth_service.py` |
| S-H8 | Redis has no authentication | `docker-compose.yml` |

### Medium

| # | Issue | File |
|---|-------|------|
| S-M1 | Faculty schedule ownership not verified on attendance endpoints | `routers/attendance.py:192-237` |
| S-M2 | Presence router faculty permission TODO not implemented | `routers/presence.py:313-316` |
| S-M3 | Android uses cleartext HTTP (no HTTPS) | `di/NetworkModule.kt` |
| S-M4 | Android tokens stored in unencrypted DataStore | `data/api/TokenManager.kt` |
| S-M5 | Android logs request/response bodies in production | `di/NetworkModule.kt:32-34` |
| S-M6 | No UUID validation on path parameters (causes 500 errors) | Multiple routers |
| S-M7 | Swagger docs exposed in production | `main.py` |
| S-M8 | `FaceRecognizeRequest.image` has no size limit | `schemas/face.py:143-147` |
| S-M9 | `python-jose` dependency has known CVEs | `requirements.txt:23` |
| S-M10 | Dozzle log viewer exposed to internet without auth | `deploy/docker-compose.prod.yml:141` |

---

## 2. BACKEND CORE & API (33 findings)

### Critical

| # | Issue | File |
|---|-------|------|
| B-C1 | Adaptive threshold ceiling (0.30) < floor (0.35) — logic inversion | `config.py:65-66` |

### High

| # | Issue | File |
|---|-------|------|
| B-H1 | Pydantic v1 `.from_orm()` calls will fail on Pydantic v2 | `routers/users.py:178,221,253,289` |
| B-H2 | `datetime.utcnow()` deprecated since Python 3.12 | `utils/security.py:68-72` |
| B-H3 | No database pool size configuration (default 5) | `database.py:18` |
| B-H4 | Deprecated `on_event()` lifecycle hooks | `main.py:94,358` |
| B-H5 | Application continues running after DB connection failure at startup | `main.py:109-111` |
| B-H6 | Notification route ordering may break with future GET endpoint | `routers/notifications.py` |

### Medium

| # | Issue | File |
|---|-------|------|
| B-M1 | `check_db_connection` leaks session on exception | `database.py:62-77` |
| B-M2 | In-memory request dedup cache unbounded + per-worker only | `routers/face.py:265-293` |
| B-M3 | APScheduler runs sync DB inside async function (blocks event loop) | `main.py:221-333` |
| B-M4 | `get_database()` returns generator, not session | `utils/dependencies.py:30-39` |
| B-M5 | Rooms DELETE does hard-delete instead of soft-delete | `routers/rooms.py:170-189` |
| B-M6 | Redis pool never replaced after connection death | `redis_client.py:12-26` |
| B-M7 | Deprecated `declarative_base()` import | `database.py:12` |
| B-M8 | Double WebSocket delivery via Redis pub/sub in single-worker | `routers/websocket.py:54-67` |

---

## 3. BUSINESS LOGIC & SERVICES (21 findings)

### High

| # | Issue | File |
|---|-------|------|
| BL-H1 | Confidence field mismatch: `get("similarity")` vs key `"confidence"` — all presence logs have NULL confidence | `presence_service.py:482,542` |
| BL-H2 | FAISS index has NO thread safety — concurrent add/search causes data races | `ml/faiss_manager.py` (entire file) |
| BL-H3 | FAISS rollback on DB failure is ineffective (vectors remain orphaned) | `face_service.py:206-208` |

### Medium

| # | Issue | File |
|---|-------|------|
| BL-M1 | `reregister_face` creates stale FAISS IDs in DB after rebuild | `face_service.py:334-345` |
| BL-M2 | Multiple DB commits per scan cycle (80+ for 40 students per 15s) | `presence_service.py:469-586` |
| BL-M3 | `asyncio.Lock` used across APScheduler threads | `presence_service.py:115` |
| BL-M4 | Stale attendance object read-then-update (lost updates possible) | `presence_service.py:557-563` |
| BL-M5 | `_redis_clear_room` passes schedule_id instead of room_id | `presence_service.py:348` |
| BL-M6 | Frame grabber reconnect race condition | `frame_grabber.py:83-91` |
| BL-M7 | Refresh token error swallowing masks DB failures as auth errors | `auth_service.py:296-298` |
| BL-M8 | FAISS IDs in DB stale after rebuild | `faiss_manager.py:380-392` |
| BL-M9 | Repository `update()` methods can't set fields to NULL | Multiple repositories |
| BL-M10 | Registration race condition (TOCTOU on duplicate check) | `auth_service.py:186-192` |

### Low

| # | Issue | File |
|---|-------|------|
| BL-L1 | Division by zero if embedding norm is zero | `face_service.py:131-133` |
| BL-L2 | FFmpeg stderr silenced (no diagnostics) | `frame_grabber.py:133` |
| BL-L3 | warmup_frames not reset on reconnect | `frame_grabber.py:177-199` |
| BL-L4 | `_ended_sessions` set grows unboundedly | `presence_service.py:114` |
| BL-L5 | ONNX session options patching is dead code | `insightface_model.py:107-114` |

---

## 4. ANDROID APP (25 findings)

### Critical

| # | Issue | File |
|---|-------|------|
| A-C1 | Hardcoded birthdate `"2000-01-01"` in registration | `RegisterReviewScreen.kt:217` |
| A-C2 | `TokenManager` uses `runBlocking` on main thread — ANR risk | `TokenManager.kt:27-38` |
| A-C3 | Navigation URL injection via special characters in names | `Routes.kt:82-89` |
| A-C4 | LiveAttendance passes empty `roomId` to LiveFeed — camera broken | `FacultyLiveAttendanceScreen.kt:136` |

### High

| # | Issue | File |
|---|-------|------|
| A-H1 | `ResetPasswordViewModel` does not call API (hardcoded success) | `ResetPasswordViewModel.kt:34-36` |
| A-H2 | `refresh()` pattern sets `isRefreshing=false` before load completes | 5+ ViewModels |
| A-H3 | `RegistrationDataHolder` stores plaintext password in static singleton | `RegistrationDataHolder.kt` |
| A-H4 | Bitmap memory leak — 5 full-res camera bitmaps never recycled | `RegistrationViewModel.kt:37` |
| A-H5 | Token refresh race condition — multiple 401s trigger parallel refreshes | `TokenAuthenticator.kt` |
| A-H6 | `AttendanceWebSocketClient` leaks OkHttpClient thread pools | `AttendanceWebSocketClient.kt:37-40` |

### Medium

| # | Issue | File |
|---|-------|------|
| A-M1 | FacultyLiveFeed `initialized` flag prevents re-init with different schedule | `FacultyLiveFeedViewModel.kt:57` |
| A-M2 | Phone validation always required in Edit Profile (should be optional) | `StudentEditProfileViewModel.kt:135` |
| A-M3 | Faculty logout has no confirmation dialog (student has one) | `FacultyProfileScreen.kt:265` |
| A-M4 | History records don't show subject name | `StudentHistoryScreen.kt` |
| A-M5 | `EmailVerificationScreen` imported but not in navigation graph | `IAMSNavHost.kt` |
| A-M6 | CameraX context cast to LifecycleOwner (unsafe) | `FaceScanScreen.kt:212`, `FaceCaptureView.kt:120` |
| A-M7 | WebSocket client no reconnect after server-initiated close | `AttendanceWebSocketClient.kt:120-123` |
| A-M8 | Rapid `connect()` calls orphan old WebSocket | `AttendanceWebSocketClient.kt:62-67` |

---

## 5. DATABASE & SCHEMA (23 findings)

### Critical

| # | Issue | File |
|---|-------|------|
| D-C1 | 3 repository files import non-existent model modules (crash on import) | `repositories/anomaly_repository.py`, `engagement_repository.py`, `prediction_repository.py` |
| D-C2 | `supabase_user_id` column exists in DB but missing from User model | `models/user.py` |
| D-C3 | Alembic env.py missing newer model imports — schema drift risk | `alembic/env.py:18-22` |

### High

| # | Issue | File |
|---|-------|------|
| D-H1 | `datetime.utcnow` used as column default (deprecated, naive timezone) | 11 model files |
| D-H2 | No `ondelete="CASCADE"` on most foreign keys | Multiple models |
| D-H3 | All User model relationships commented out | `models/user.py:73-77` |
| D-H4 | No connection pool configuration (`pool_size`, `pool_recycle`) | `database.py:18` |
| D-H5 | Supabase RLS disabled on all tables — anon key bypasses API | All tables |

### Medium

| # | Issue | File |
|---|-------|------|
| D-M1 | `get_summary()` fetches all rows, counts in Python (should aggregate in SQL) | `attendance_repository.py:154-191` |
| D-M2 | No eager loading — N+1 queries everywhere | All repositories |
| D-M3 | Race condition in user create duplicate check (TOCTOU) | `user_repository.py:92-101` |
| D-M4 | No `updated_at` column on most tables | Multiple models |
| D-M5 | Room table missing unique constraint on (name, building) | `models/room.py` |
| D-M6 | `schedule.day_of_week` lacks CHECK constraint (0-6) | `models/schedule.py:50` |
| D-M7 | Migration chain integrity — 16 files on disk, 6 applied | `alembic/versions/` |

---

## 6. WEBSOCKET & REAL-TIME (22 findings)

### Critical

| # | Issue | File |
|---|-------|------|
| W-C1 | No authentication on either WebSocket endpoint | `routers/websocket.py:160-181` |
| W-C2 | Android WebSocket client sends no auth token | `AttendanceWebSocketClient.kt:70-72` |

### High

| # | Issue | File |
|---|-------|------|
| W-H1 | Sync Redis + sync DB inside async code blocks event loop | `presence_service.py:164-175,412-598` |
| W-H2 | Early leave events in new pipeline NOT persisted to DB | `track_presence_service.py:209-226` |
| W-H3 | DB session open for entire pipeline lifetime (hours) | `realtime_pipeline.py:52-186` |
| W-H4 | Double delivery in multi-worker mode | `websocket.py:54-66,115-145` |
| W-H5 | No queuing for offline alert recipients | `websocket.py:68-76` |
| W-H6 | Unhandled exceptions leak dead connections in broadcast set | `websocket.py:163-169` |

### Medium

| # | Issue | File |
|---|-------|------|
| W-M1 | Set mutation during broadcast iteration | `websocket.py:57-63` |
| W-M2 | No Android client for alerts WebSocket | N/A |
| W-M3 | No reconnect after server-initiated WebSocket close | `AttendanceWebSocketClient.kt:120-123` |
| W-M4 | Schedule queried every frame at 10fps (36K queries/hour) | `track_presence_service.py:136` |
| W-M5 | Class-level mutable state accessed without lock | `presence_service.py:113-114` |

---

## 7. DEVOPS & DEPLOYMENT (37 findings)

### Critical

| # | Issue | File |
|---|-------|------|
| DV-C1 | Camera RTSP credentials hardcoded in git-tracked configs | `deploy/mediamtx.dev.yml:60-80` |
| DV-C2 | Same JWT SECRET_KEY in dev and production .env | `.env` / `.env.production` |
| DV-C3 | Production DB uses `iams_dev_password` | `.env.production:10` |
| DV-C4 | Backend Dockerfile runs as root | `backend/Dockerfile` |
| DV-C5 | CORS wildcard in production config | `.env.production:19` |
| DV-C6 | `python-jose` has known CVEs | `requirements.txt:23` |

### High

| # | Issue | File |
|---|-------|------|
| DV-H1 | No HTTPS (nginx SSL block commented out) | `deploy/nginx.conf:18-31` |
| DV-H2 | No nginx security headers | `deploy/nginx.conf` |
| DV-H3 | Redis has no authentication password | `docker-compose.yml:40` |
| DV-H4 | Deploy script has zero-downtime gap (down then up) | `deploy/deploy.sh:79-84` |
| DV-H5 | Deploy always rebuilds with `--no-cache` (slow, long downtime) | `deploy/deploy.sh:77` |
| DV-H6 | Dozzle log viewer exposed to internet on port 9999 | `deploy/docker-compose.prod.yml:141` |
| DV-H7 | TURN credentials are weak and inconsistent between configs | `docker-compose.yml:76` vs `mediamtx.yml:65` |

### Medium

| # | Issue | File |
|---|-------|------|
| DV-M1 | No database backup strategy | No backup scripts/configs |
| DV-M2 | No FAISS data backup | `deploy/docker-compose.prod.yml:52` |
| DV-M3 | No Docker log rotation | `deploy/docker-compose.prod.yml` |
| DV-M4 | `mediamtx:latest` and `coturn:latest` unpinned | Both compose files |
| DV-M5 | No rollback mechanism in deploy script | `deploy/deploy.sh` |
| DV-M6 | Test/lint dependencies included in production image | `requirements.txt:62-68` |
| DV-M7 | Edge health check references wrong variable name | `edge/scripts/health_check.sh:64` |
| DV-M8 | Edge has dual competing configuration systems | `edge/app/config.py` vs `edge/.env` |
| DV-M9 | Dev Compose exposes PostgreSQL on 0.0.0.0:5432 with password "123" | `docker-compose.yml:20,26-27` |

---

## Remediation Priority

### Phase 1: Before Any Production Use (CRITICAL)
1. Rotate ALL secrets — JWT key, DB password, TURN credentials, EDGE_API_KEY
2. Add JWT auth to WebSocket endpoints
3. Enforce EDGE_API_KEY on `/face/process`, `/face/gone`
4. Enable HTTPS on nginx
5. Add `USER appuser` to Dockerfile
6. Lock down CORS origins
7. Add rate limiting to login/register/refresh
8. Fix adaptive threshold ceiling < floor inversion
9. Create missing model files (anomaly, engagement, prediction)
10. Fix confidence field mismatch (`"similarity"` → `"confidence"`)

### Phase 2: Next Sprint (HIGH)
1. Add FAISS thread safety (RLock)
2. Fix Android `TokenManager` `runBlocking` → in-memory cache
3. URL-encode navigation arguments in Routes.kt
4. Fix `RegistrationDataHolder` to include birthdate
5. Fix empty `roomId` in FacultyLiveAttendanceScreen
6. Implement refresh token rotation
7. Fix privilege escalation (faculty scope)
8. Add `pool_size`/`pool_recycle` to DB engine
9. Enable Supabase RLS on all tables
10. Set up database backups

### Phase 3: Before Thesis Defense (MEDIUM)
1. Fix N+1 queries with eager loading
2. Batch DB commits in presence scan cycle
3. Fix async/sync mixing in presence service
4. Add ondelete CASCADE to foreign keys
5. Implement ResetPasswordViewModel API call
6. Add confirmation dialog to faculty logout
7. Pin Docker image versions
8. Add Docker log rotation
9. Split requirements.txt (prod vs dev)
10. Fix deploy script zero-downtime gap
