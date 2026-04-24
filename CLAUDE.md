# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

---

## What IAMS is

CCTV-based facial-recognition attendance system for JRMSU. Three clients share one
backend: a React + Vite **admin portal**, a Kotlin **student** APK, and a
Kotlin **faculty** APK. The system was split on 2026-04-22 so that heavy
work (ML, face embeddings, attendance tracking) runs on an on-prem Mac on
IAMS-Net, and the VPS becomes a thin public face for the faculty app.

Keep these invariants in mind before editing anything:

- **Faculty app is always VPS-bound.** Off-campus watching is its reason
  to exist. `switch-env.sh` does not touch faculty keys; its `gradle.properties`
  entries are hard-pinned to `167.71.217.44`.
- **Student app + admin portal are on-prem-only.** Both hit the Mac backend,
  which owns all student PII + face embeddings. Neither talks to the VPS API
  (the VPS doesn't have student data anyway — feature-flagged off).
- **Two Android Gradle modules**, one `:app-student` and one `:app-faculty`,
  produce two distinct APKs (`com.iams.app.student` + `com.iams.app.faculty`).
  They install side-by-side on a phone.

---

## System architecture (as it runs today)

```
┌── On-Campus / IAMS-Net ──────────────────────────────────────────────┐
│                                                                       │
│  Reolink EB226 (192.168.88.10)  Reolink EB227 (192.168.88.11)         │
│               │                            │                          │
│               │   ffmpeg supervisor on the Mac                        │
│               │   (scripts/iams-cam-relay.sh, nohup+disown)           │
│               v                            v                          │
│        rtsp://localhost:8554/eb226, /eb227                            │
│                        (Mac's mediamtx-onprem)                        │
│                                  │                                    │
│        ┌─────────────────────────┼──────────────────────────────┐     │
│        │ api-gateway             │ admin portal (Vite dev       │     │
│        │ frame_grabber           │    or built-static served    │     │
│        │ ↓                       │    by nginx-onprem)          │     │
│        │ SCRFD → ByteTrack       │    → WHEP @ :8889/<key>/whep │     │
│        │ ↓                       │    → WS @ /api/v1/ws/...     │     │
│        │ ArcFace → FAISS         │    → REST @ /api/v1/*        │     │
│        │ ↓                       │                              │     │
│        │ WebSocket broadcast     │ runOnReady ffmpeg  ───┐      │     │
│        └─────────────────────────┴───────────────────────┼──────┘     │
│                                                          │            │
│  Student APK (com.iams.app.student) ← IAMS-Net only      │            │
│    → http://<MAC_IP>/api/v1/* (REST + WS)                │            │
│    → face registration, schedule, history, attendance    │            │
│                                                          │ -c copy    │
└──────────────────────────────────────────────────────────┼────────────┘
                                                           │
                                                           │ outbound RTSP push
                                                           │ (no re-encode)
                                                           v
┌── VPS 167.71.217.44 — thin API + public relay ───────────────────────┐
│                                                                       │
│  mediamtx (:8554 ingest from Mac, :8889 WHEP out)                     │
│  coturn   (:3478 / UDP 49152-49252) — TURN for mobile NAT             │
│  postgres (faculty + schedules + rooms ONLY)                          │
│  api-gateway (same image, ENABLE_ML=false etc.)                       │
│    → /api/v1/auth/*         (faculty login)                           │
│    → /api/v1/schedules/me   (faculty's schedules)                     │
│    → /api/v1/rooms/{id}     (stream_key lookup)                       │
│    → /api/v1/health                                                   │
│    (face/attendance/presence/analytics/notifications/ws → 404)        │
│  nginx (:80 /api proxy + /iams-{student,faculty}.apk)                 │
│  dozzle (:9999)                                                       │
│                                                                       │
│  Faculty APK (com.iams.app.faculty) ← works anywhere with internet    │
│    → POST /api/v1/auth/login                                          │
│    → GET /api/v1/schedules/me                                         │
│    → http://167.71.217.44:8889/<stream_key>/whep  (live video)        │
└───────────────────────────────────────────────────────────────────────┘
```

## What runs on which machine

| Machine | Service | Purpose |
|---|---|---|
| **Mac on IAMS-Net** | `iams-postgres-onprem` | Full DB — users, faces, schedules, attendance, presence logs |
|  | `iams-redis-onprem` | Identity cache + WS pub/sub |
|  | `iams-mediamtx-onprem` | RTSP ingest from ffmpeg supervisor; WHEP out to admin; RTSP out to api-gateway frame_grabber; `runOnReady` push to VPS |
|  | `iams-api-gateway-onprem` | FastAPI: auth, face recognition, attendance, WebSocket broadcast, APScheduler (session lifecycle + digests). All `ENABLE_*` flags true. |
|  | `iams-nginx-onprem` | Serves the admin SPA + proxies `/api/*`, `/api/v1/ws/*`, `/whep/*` |
|  | `iams-admin-build-onprem` | One-shot sidecar: `npm run build -- --mode onprem`; exits 0 when done |
|  | `iams-dozzle-onprem` | Log viewer @ `http://localhost:9998/` |
|  | Host ffmpeg supervisor | `scripts/iams-cam-relay.sh` — pulls Reolink main-stream RTSP, pushes to local mediamtx |
| **VPS 167.71.217.44** | `iams-api-gateway` | Same backend image as the Mac, but with `ENABLE_ML=false`, `ENABLE_FACE_ROUTES=false`, etc. Only auth / users / schedules / rooms / health routers remain. |
|  | `iams-postgres` | Minimal DB: faculty users + schedules + rooms + admin. Seeded by `backend/scripts/seed_vps_minimal.py`. |
|  | `iams-mediamtx` | Receives runOnReady push from the Mac; serves public WHEP to the Faculty APK. |
|  | `iams-coturn` | WebRTC NAT traversal for phones on cellular. |
|  | `iams-nginx` | Proxy `/api/*` to api-gateway; serve APK downloads. |
|  | `iams-dozzle` | Logs @ `http://167.71.217.44:9999/`. |

`docker-compose.yml` (local dev stack, no `-onprem` suffix) still exists as
a dev-iteration convenience but is **not** what you want running day-to-day.
It conflicts with the onprem stack on ports 5432/6379/8554/8889 — both
cannot run at the same time.

---

## Daily runtime flow

After a Mac reboot / Docker Desktop restart / stale-state recovery:

```bash
cd ~/Projects/iams
./scripts/dev-down.sh           # safety — stops the dev stack if it's up
./scripts/onprem-up.sh          # brings up postgres+redis+mediamtx+api-gateway+nginx+admin-build+dozzle
./scripts/start-cam-relay.sh    # starts Reolink → mediamtx ffmpeg supervisor (idempotent)
```

`./scripts/onprem-up.sh` auto-sources `scripts/.env.local` (gitignored) to
pick up `POSTGRES_PASSWORD` — see the "Secrets + first-time setup" section
below. Without this, compose substitutes the default fallback password
and api-gateway can't authenticate to the already-seeded postgres volume.

To watch the classroom live:

- **Admin portal** (full overlays + attendance + start/end): open
  `http://localhost:5173/` in a browser on this Mac (Vite dev), or
  `http://192.168.88.17/` from any LAN browser, then navigate
  **Schedules → click a schedule → Watch Live**. The live feed page is at
  `/schedules/<id>/live`.
- **Faculty APK** (pure viewer): open on any phone with internet; log in
  with `maricon.gahisan@jrmsu.edu.ph` / `password123` → tap a class.

To stop everything when closing shop for the day:

```bash
./scripts/stop-cam-relay.sh
./scripts/onprem-down.sh
```

Volumes are preserved (postgres data, FAISS index, InsightFace models,
admin build output), so the next `onprem-up.sh` comes back with all state
intact.

---

## Secrets + first-time setup

Three env files are in play. Only the first two are gitignored.

| File | Purpose |
|---|---|
| `backend/.env.onprem` | FastAPI config on the Mac: `SECRET_KEY`, `RECOGNITION_THRESHOLD`, `INSIGHTFACE_MODEL`, etc. |
| `backend/.env.vps`    | FastAPI config on the VPS: everything above plus `ENABLE_*=false` flags. |
| `scripts/.env.local`  | **Per-operator secrets sourced by shell scripts.** Currently: `POSTGRES_PASSWORD`. Sourced automatically by `onprem-up.sh` + `deploy.sh`. |

### Fresh-clone setup

```bash
# 1. Backend envs — generate unique SECRET_KEYs
cp backend/.env.onprem.example backend/.env.onprem
cp backend/.env.vps.example     backend/.env.vps
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into both
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # pick POSTGRES_PASSWORD

# 2. Shell-sourced secret
cp scripts/.env.local.example scripts/.env.local
$EDITOR scripts/.env.local     # paste POSTGRES_PASSWORD here

# 3. Admin portal env
cp admin/.env.production.example admin/.env.production
```

**Critical**: the `POSTGRES_PASSWORD` in `scripts/.env.local` must match
the value baked into the `postgres_data_onprem` Docker volume on the FIRST
`onprem-up.sh` boot. If you ever rotate it without also rotating inside
postgres, the api-gateway will fail with "password authentication failed".
Easy recovery: `./scripts/onprem-down.sh --purge` + re-seed.

---

## Deploying to VPS

```bash
bash deploy/deploy.sh vps    # default: thin API + mediamtx + coturn + nginx + dozzle
bash deploy/deploy.sh relay  # fallback: video-only relay (no API)
bash deploy/deploy.sh full   # legacy pre-split rollback
```

`deploy.sh` auto-sources `scripts/.env.local` for the same
`POSTGRES_PASSWORD`. After a successful deploy, seed runs automatically
via:

```bash
ssh root@167.71.217.44 'docker exec iams-api-gateway-vps python -m scripts.seed_vps_minimal'
```

### Verify a VPS deploy

```bash
curl http://167.71.217.44/api/v1/health                # 200, ENABLE_* reflected
curl -X POST http://167.71.217.44/api/v1/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"identifier":"maricon.gahisan@jrmsu.edu.ph","password":"password123"}'
curl http://167.71.217.44/api/v1/face/register         # expect 404 (ENABLE_FACE_ROUTES=false)
ssh root@167.71.217.44 'docker logs --tail 80 iams-api-gateway-vps'
```

---

## The camera stream supervisor

The Reolink cameras publish RTSP on IAMS-Net. On macOS 26 Tahoe, a
LaunchAgent-spawned ffmpeg is silently blocked by Local-Network TCC from
reaching `192.168.88.x` — but an ffmpeg spawned by a Terminal-descendant
shell is fine. So the supervisor runs under a nohup+disown shell, not
launchd.

Files:

| File | Role |
|---|---|
| [scripts/iams-cam-relay.sh](scripts/iams-cam-relay.sh) | Supervisor. Hardcodes the 2 cameras + credentials, loops ffmpeg with 3 s reconnect, traps SIGTERM for clean child teardown. |
| [scripts/start-cam-relay.sh](scripts/start-cam-relay.sh) | `nohup ... disown` launcher. Idempotent — kills any existing supervisor before starting. Writes PID file. |
| [scripts/stop-cam-relay.sh](scripts/stop-cam-relay.sh) | SIGTERM → SIGKILL fallback. `pkill`s orphan ffmpegs defensively. |
| [scripts/Start IAMS Camera Relay.command](scripts/Start%20IAMS%20Camera%20Relay.command) | Double-clickable entry to use as a **Login Item** (System Settings → General → Login Items). Opens Terminal, runs `start-cam-relay.sh`, survives terminal-close. |

Log: `~/Library/Logs/iams-cam-relay.log`.

**Known tradeoff**: the supervisor dies on Mac sleep + reboot. For
reboot-persistence without ceremony, add the `.command` file to Login
Items once. A proper LaunchAgent would need a code-signed ffmpeg — out of
scope for the thesis.

---

## Face recognition tuning

On the on-prem Mac (`backend/.env.onprem`):

```
INSIGHTFACE_MODEL=buffalo_l
INSIGHTFACE_DET_SIZE=960
INSIGHTFACE_DET_THRESH=0.3
```

History of pain:

- `buffalo_s` at thresh 0.5 missed classroom-distance faces (~40 px wide).
  Escalated to `buffalo_l` and dropped thresh to 0.3 on 2026-04-22 (this
  matches the VPS production profile that shipped pre-split).
- `det_size` bumped 640 → 960 on 2026-04-24 because EB226 (wider lens
  than EB227) was reporting `Tracks: 0` with a seated person clearly
  visible. At det_size=640 a 1280×720 grab gets scaled 2:1 inside SCRFD,
  so a ~40 px face shrinks to ~20 px — below the reliable detection
  floor. 960 lowers the internal scale to 0.75× at ~2.2× CPU cost. The
  M5 has the headroom and attendance only needs one hit per 60-s scan.
- The ffmpeg supervisor pushes TWO profiles per camera to local mediamtx:
  **`h264Preview_01_main`** → `<stream_key>` (≈2304×1296, what the ML
  pipeline decodes) and **`h264Preview_01_sub`** → `<stream_key>-sub`
  (≈640×360, what the admin portal's WHEP player decodes). SCRFD still runs
  on main — the sub profile was too small for classroom-distance faces.
  The sub profile is admin-display-only; it is NOT forwarded to the VPS
  (the faculty APK consumes main via the runOnReady relay). See the
  `~^.+-sub$` path rule in [deploy/mediamtx.onprem.yml](deploy/mediamtx.onprem.yml).

At `buffalo_l` on CPU (M5), the real-time pipeline tops out around
0.5-1 fps. The admin portal's `DetectionOverlay` smooths this with a
snap-then-lerp interpolator so boxes still feel responsive.

Face registration (student APK → CameraX → upload) uses the same model
server-side, so registered embeddings live in the same FAISS index and
identity resolves immediately without a separate reindex.

---

## Backends in lockstep

Both backends share:

- The same Dockerfile, image, routers, Pydantic schemas, SQLAlchemy models.
- The `ENABLE_*` feature flags in `backend/app/config.py` (see
  [backend/app/main.py](backend/app/main.py) router-include block).
- `seed_data.py` constants (`FACULTY_RECORDS`, `ROOM_DEFS`, `SCHEDULE_DEFS`).

What diverges:

| | On-prem Mac | VPS |
|---|---|---|
| Seed script | `scripts/seed_data.py` (everything) | `scripts/seed_vps_minimal.py` (faculty+schedules+rooms only) |
| Redis | yes | no (`ENABLE_REDIS=false`) |
| ML stack | yes | no (`ENABLE_ML=false`) |
| Frame grabbers | yes | no (`ENABLE_FRAME_GRABBERS=false`) |
| APScheduler | yes | no (`ENABLE_BACKGROUND_JOBS=false`) |
| Active routers | auth+users+face+schedules+rooms+analytics+attendance+presence+notifications+audit+edge+settings+ws+health | auth+users+schedules+rooms+health |

The VPS postgres holds the same `faculty_records`, `users` (faculty+admin
rows), `schedules`, and `rooms` rows as the Mac. It does NOT hold
students, enrollments, face embeddings, attendance records, presence logs,
or early-leave events.

If you add a new real schedule to `SCHEDULE_DEFS` in
`backend/scripts/seed_data.py`, both stacks pick it up on their next seed:

```bash
# Re-seed on-prem
docker exec iams-api-gateway-onprem python -m scripts.seed_data

# Re-seed VPS
bash deploy/deploy.sh vps     # `deploy.sh` auto-re-runs seed_vps_minimal
```

---

## The big session-lifecycle auto-start/end

`backend/app/main.py` runs `session_lifecycle_check` every 15 seconds. It:

1. Pulls schedules whose `(day_of_week, start_time..end_time)` window
   contains `datetime.now()` and isn't already active → **auto-starts** a
   SessionPipeline for each (creates a FrameGrabber if the room doesn't
   have one already).
2. Pulls active sessions whose `end_time` is in the past → **auto-ends**
   them (tears down the pipeline; keeps the FrameGrabber if another
   back-to-back session in the same room starts within 15 s).

The rolling 30-min test schedules (`EB226-HHMM` / `EB227-HHMM`) use this
to exercise the full PRESENT / LATE / ABSENT / EARLY_LEAVE state machine
all day. Real faculty schedules ride the same code path.

This means "click Start Session" in the admin portal is usually
**unnecessary**: once the schedule window opens, the session appears by
itself. The button exists for (a) manual sessions outside the normal
window, (b) restart recovery, (c) explicit demo control.

---

## Android apps structure

After the 2026-04-22 two-app split:

```
android/
├── settings.gradle.kts          # include(":app-student"), include(":app-faculty")
├── gradle.properties            # IAMS_STUDENT_*, IAMS_FACULTY_*
│
├── app-student/                 # applicationId com.iams.app.student
│   └── src/main/java/com/iams/app/
│       ├── IAMSApplication.kt   # @HiltAndroidApp
│       ├── MainActivity.kt       # mounts IAMSNavHost
│       ├── di/NetworkModule.kt
│       ├── data/api/             # ApiService (full), Auth*, NotificationService,
│       │                         #   PendingFaceUploadManager, TokenManager
│       ├── data/model/Models.kt  # All DTOs
│       ├── ui/onboarding/        # Splash, Onboarding, Welcome
│       ├── ui/auth/              # StudentLogin, registration (4 steps), forgot/reset pw
│       ├── ui/student/           # Home, Schedule, History, Profile, Analytics …
│       ├── ui/components/        # Theme + FaceCaptureView/FaceScanScreen
│       └── ui/navigation/
│
└── app-faculty/                 # applicationId com.iams.app.faculty
    └── src/main/java/com/iams/app/
        ├── IAMSApplication.kt    # minimal @HiltAndroidApp
        ├── MainActivity.kt       # mounts FacultyNavHost
        ├── di/NetworkModule.kt   # same shape, BACKEND_HOST always 167.71.217.44
        ├── data/api/             # ApiService subset
        ├── ui/auth/              # FacultyWelcome + FacultyLogin
        ├── ui/faculty/           # Schedules list + LiveFeed pure-viewer
        ├── ui/components/        # Shared UI
        │   └── NativeWebRtcVideoPlayer.kt
        ├── webrtc/               # WhepClient, WhepConnectionState
        └── ui/navigation/        # FacultyNavHost + FacultyRoutes
```

Build:

```bash
cd android
./gradlew :app-student:assembleDebug    # ~35 MB APK
./gradlew :app-faculty:assembleDebug    # ~32 MB APK
./gradlew :app-student:installDebug :app-faculty:installDebug
```

Android `gradle.properties` has TWO namespaces:

- `IAMS_STUDENT_BACKEND_HOST` / `IAMS_STUDENT_BACKEND_PORT` — toggled by
  `scripts/switch-env.sh`. Points the student APK at the Mac on IAMS-Net.
- `IAMS_FACULTY_API_HOST` / `IAMS_FACULTY_API_PORT` / `IAMS_FACULTY_STREAM_HOST`
  — **hard-pinned to `167.71.217.44`**. Never touched by switch-env. The
  faculty app is always VPS-bound by design.

---

## Tech quick reference

### Backend
- FastAPI + SQLAlchemy (Postgres) + Redis (identity cache)
- InsightFace (`buffalo_l`): SCRFD for detection + ArcFace for recognition
- FAISS `IndexFlatIP` with 512-dim L2-normalised ArcFace embeddings
- ByteTrack for tracker IDs, 10 fps pipeline on the Mac (CPU-only)
- APScheduler for session lifecycle, digests, anomaly detection

### Admin portal
- React 19 + Vite + TypeScript, Radix UI + Tailwind, TanStack Query, Zustand
- Live feed page = native `RTCPeerConnection` WHEP client + HTML `<canvas>`
  overlay fed by `/api/v1/ws/attendance/{schedule_id}`
- Snap-then-lerp interpolation so boxes are smooth even at slow backend fps

### Android
- Kotlin + Jetpack Compose + Material 3, Hilt, Retrofit + OkHttp, DataStore
- Student: CameraX + ML Kit Face Detection for multi-angle capture
- Faculty: `stream-webrtc-android` WHEP viewer; no ML Kit, no CameraX

### Infrastructure
- mediamtx for RTSP ingest + WebRTC WHEP serving
- coturn for WebRTC NAT traversal (faculty phones off-campus)
- nginx as the admin portal static host + `/api/` reverse proxy

---

## Database schema (core tables)

- `users` — role = student / faculty / admin (Postgres enum: labels are
  UPPERCASE because SQLAlchemy serialises `.name` not `.value`; raw SQL
  that compares to lowercase will fail — see the 2026-04-22 seed_vps bug
  for history)
- `face_registrations`, `face_embeddings` — on the Mac only
- `rooms`, `schedules`, `enrollments`
- `attendance_records`, `presence_logs`, `early_leave_events` — on the Mac only

---

## Debugging + logs

On the Mac:

- Dozzle: `http://localhost:9998/`
- Direct: `docker compose -f deploy/docker-compose.onprem.yml logs -f api-gateway`
- Mediamtx API: `docker exec iams-mediamtx-onprem wget -qO- http://localhost:9997/v3/paths/list`
- Live WebSocket tap (from inside container, for verification):

  ```bash
  TOKEN=$(curl -sS -X POST http://localhost/api/v1/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"identifier":"admin@admin.com","password":"123"}' \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  SCHED=<schedule-uuid>
  docker exec iams-api-gateway-onprem python3 -c "
  import asyncio, json, websockets
  async def tail():
      async with websockets.connect(
          'ws://localhost:8000/api/v1/ws/attendance/${SCHED}?token=${TOKEN}'
      ) as ws:
          for _ in range(20):
              print(json.loads(await ws.recv()))
  asyncio.run(tail())"
  ```

On the VPS:

- Dozzle: `http://167.71.217.44:9999/`
- Direct: `ssh root@167.71.217.44 'docker logs --tail 100 iams-api-gateway-vps'`

---

## Common pitfalls (known gotchas)

- **Dev stack vs on-prem stack collision.** Both use ports 5432 / 6379 /
  8554 / 8889. Only one can run. Always `./scripts/dev-down.sh` before
  `./scripts/onprem-up.sh` after any Docker Desktop restart.
- **Forgetting to source `scripts/.env.local` before `docker compose`.**
  Don't run raw compose commands — use the scripts. They auto-source the
  password file so postgres auth doesn't mismatch.
- **Faculty APK "login OK but 0 schedules".** The test accounts
  (`faculty.eb226@gmail.com` / `faculty.eb227@gmail.com`) don't own any
  real schedules (only the rolling test slots, which VPS seed skips). Use
  one of the three real faculty (`ryan.elumba@jrmsu.edu.ph`,
  `maricon.gahisan@jrmsu.edu.ph`, `troy.lasco@jrmsu.edu.ph`).
- **`live.tsx` sessions/active parsing.** The backend returns
  `active_sessions: ["uuid1", "uuid2", ...]` (flat list of strings). The
  admin portal uses `.includes(scheduleId)`. Don't revert that to `.some(s
  => s.schedule_id === ...)` — it's wrong (was the "Session not running
  stays after Start" bug on 2026-04-22).
- **`buffalo_l` model download needs a writeable volume.** If you see
  `PermissionError: '/home/appuser/.insightface/models/buffalo_s.zip'`,
  the entrypoint's chown list is missing that path. Fixed in
  `backend/entrypoint.sh` on 2026-04-22.
- **`runOnReady` needs ffmpeg inside mediamtx.** The Alpine
  `bluenviron/mediamtx` image has no `sh` and no `ffmpeg`. The onprem
  compose uses the `-ffmpeg` variant for this reason.

---

## Plan Mode: lesson capture

Every plan must end with a `## Lessons` section. First execution step
after exiting plan mode is to append those lessons to `memory/lessons.md`
so they survive into future sessions:

```
## YYYY-MM-DD: Short title
What happened, why it matters, what to do differently.
```

---

## Where the design docs are

- [docs/plans/2026-04-21-local-compute-split/DESIGN.md](docs/plans/2026-04-21-local-compute-split/DESIGN.md)
- [docs/plans/2026-04-21-local-compute-split/RUNBOOK.md](docs/plans/2026-04-21-local-compute-split/RUNBOOK.md)
- [docs/plans/2026-04-22-two-app-split/DESIGN.md](docs/plans/2026-04-22-two-app-split/DESIGN.md)
- [docs/plans/2026-04-22-two-app-split/RUNBOOK.md](docs/plans/2026-04-22-two-app-split/RUNBOOK.md)
- [docs/main/](docs/main/) — older prd / architecture docs; some sections
  superseded by the two splits above.
