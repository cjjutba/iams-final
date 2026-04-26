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
|  | `iams-api-gateway-onprem` | FastAPI: auth, face recognition, attendance, WebSocket broadcast, APScheduler (session lifecycle + digests). All `ENABLE_*` flags true. **Realtime ML proxies to the native ML sidecar** when `ML_SIDECAR_URL` is set (default in `.env.onprem`). |
|  | `iams-nginx-onprem` | Serves the admin SPA + proxies `/api/*`, `/api/v1/ws/*`, `/whep/*` |
|  | `iams-admin-build-onprem` | One-shot sidecar: `npm run build -- --mode onprem`; exits 0 when done |
|  | `iams-dozzle-onprem` | Log viewer @ `http://localhost:9998/` |
|  | Host ffmpeg supervisor | `scripts/iams-cam-relay.sh` — pulls Reolink main-stream RTSP, pushes to local mediamtx |
|  | **Host ML sidecar** | `scripts/iams-ml-sidecar.sh` — native macOS Python process (port 8001). Loads InsightFace with `CoreMLExecutionProvider` so SCRFD + ArcFace run on the Apple Neural Engine + Metal GPU. The api-gateway in Docker proxies its realtime calls here over `host.docker.internal:8001`. |
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
./scripts/onprem-up.sh          # brings up ML sidecar + postgres+redis+mediamtx+api-gateway+nginx+admin-build+dozzle
./scripts/start-cam-relay.sh    # starts Reolink → mediamtx ffmpeg supervisor (idempotent)
```

`onprem-up.sh` now starts the **ML sidecar** as its first step (before
Docker) so the api-gateway's lifespan probe (`GET /health` on
`host.docker.internal:8554`) finds it on the first try. To skip the
sidecar and run inference in-container on CPU only, set
`IAMS_SKIP_ML_SIDECAR=1` in the environment or `scripts/.env.local`.

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
Easy recovery: `./scripts/onprem-down.sh --purge` + re-seed — but **see
the seed-data warning in the next section first**: a fresh seed wipes
every registered face. If you have working face registrations on this
Mac you do NOT want to lose, fix the password mismatch in-place
(`docker exec iams-postgres-onprem psql ... ALTER USER ...`) instead of
purging the volume.

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
RECOGNITION_THRESHOLD=0.45        # Was 0.38 until the 2026-04-25 swap
RECOGNITION_MARGIN=0.10           # Was 0.06 until the 2026-04-25 swap
ADAPTIVE_ENROLL_ENABLED=false     # Default off — see lessons.md
ADAPTIVE_ENROLL_MIN_CONFIDENCE=0.70
ADAPTIVE_ENROLL_STABLE_FRAMES=30
```

Operator workflows for the recognition layer:

| Tool | Use case |
|---|---|
| `python -m scripts.rebuild_faiss [--dry-run]` | Wipe in-memory adaptive vectors + rebuild FAISS strictly from canonical DB embeddings. Run after threshold changes or any suspected index poisoning. |
| `python -m scripts.calibrate_threshold --rooms EB226,EB227 [--csv /tmp/calib.csv]` | Sample N frames from each camera, dump per-user top-1 sim distribution, recommend threshold + margin. |
| `python -m scripts.cctv_enroll --user-id <uuid> --room EB226 --captures 5` | Add 5 CCTV-domain embeddings to a student who has phone-side registered. Closes the cross-domain gap. Operator must keep ONE student in frame. |
| `POST /api/v1/face/cctv-enroll/{user_id}` | Same as above via REST (admin-only). Reuses the always-on FrameGrabber if available. |
| `python -m scripts.preflight_session [--all-today \| --schedule-id <uuid> \| --room EB226]` | **Pre-flight readiness check.** For every enrolled student × room in scope, classify recognition coverage as READY / LIKELY OK / AT RISK / NOT REGISTERED, and emit one-line copy-paste `cctv_enroll` commands for each flagged row. Run 5-10 min before a demo or class to surface students who would appear as "Unknown" cold. Default scope = sessions whose window contains "now"; `--all-today` lists every schedule on the current day_of_week. Exit codes: 0 all READY, 1 some need attention, 2 someone is NOT REGISTERED. |

### Auto CCTV enrolment — sliding-window mode

The `AutoCctvEnroller` service captures real CCTV embeddings in the
background while sessions are running, with no operator action and no
student UI. The 2026-04-26 plan
([docs/plans/2026-04-26-auto-cctv-sliding-window/DESIGN.md](docs/plans/2026-04-26-auto-cctv-sliding-window/DESIGN.md))
upgraded the original "fill-then-stop at cap=5" design to a continuous
sliding-window architecture so the cluster can track real face drift
across a term.

How it works in practice:

1. **Fill phase.** A student is recognised in EB226 → first 5 confident,
   stable, well-spaced captures buffer → swap-safe gate runs → 5 rows
   land in `face_embeddings` with label `cctv_eb226_<idx>`. Repeat
   until the (user, room) reaches `AUTO_CCTV_ENROLL_LIFETIME_CAP=30`.
2. **Sliding-window phase.** Past the cap, every new buffered batch
   triggers eviction of the lowest-quality existing CCTV row(s) for
   that (user, room) before insert. Quality = composite of recognition
   confidence + crop sharpness (Laplacian variance). Sharper, more-
   confident captures replace blurry, less-confident ones over time.
3. **Daily throttle.** At most 2 replacement batches per (user, room)
   per UTC day, so a single bad-lighting day cannot rewrite half the
   cluster.
4. **Swap-safe gate at every commit.** For each new capture, the
   committer FAISS-searches the live index — if any other user's
   existing embeddings come closer to the capture than the claimed
   user's by more than `RECOGNITION_MARGIN`, the entire batch is
   discarded. This is the structural defence against the 2026-04-25
   identity-swap incident.

Operator knobs (in `backend/.env.onprem`, see file for full commentary):

```
AUTO_CCTV_ENROLL_LIFETIME_CAP=30                # Hard upper bound per (user, room)
AUTO_CCTV_ENROLL_REPLACEMENT_ENABLED=true       # false = legacy hard-stop at cap
AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT=2      # Batches/day past cap, per (user, room)
AUTO_CCTV_ENROLL_SWAP_SAFE_MARGIN=0.10          # Per-capture cross-user reject margin
AUTO_CCTV_ENROLL_QUALITY_CONFIDENCE_WEIGHT=0.6  # Weight on confidence in quality score
AUTO_CCTV_ENROLL_QUALITY_BLUR_WEIGHT=0.4        # Weight on sharpness in quality score
AUTO_CCTV_ENROLL_BLUR_NORM_MAX=200.0            # Laplacian variance "very sharp" ceiling
```

**FAISS deletion caveat.** `IndexFlatIP` does not support native
removal — eviction only purges the row from `face_embeddings` + the
`faiss_manager.user_map`. The orphan vector remains in the underlying
index but no top-K result can return it (no user_id maps to it).
Each eviction increments `_orphans_since_boot` on the singleton; when
that number gets large (>1000-ish, depends on student count) run
`docker exec iams-api-gateway-onprem python -m scripts.rebuild_faiss`
to compact the index. Not urgent — orphans are inert, just bloat.

Operator sanity-check the auto-enroller is doing the right thing:

```bash
docker exec iams-api-gateway-onprem grep -E "auto-cctv:" /app/logs/app.log | tail -50
```

Look for lines like:
- `buffered capture N/5 ... mode=fill` — fill phase, normal during a
  student's first sessions in a room
- `buffered capture N/5 ... mode=replace` — sliding-window phase,
  cluster is at cap and we're considering a refresh
- `COMMITTED N captures ... mode=replace ... evicted=K` — actual
  replacement happened
- `swap-safe gate failed` — a batch was discarded because one capture
  matched a different user too closely; this is the safety net working
- `daily replacement throttle reached` — (user, room) is at the daily
  budget; further refresh will resume tomorrow UTC

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
  **Don't switch the admin display to main without first decoupling readers.**
  An attempt on 2026-04-25 to default the admin to main produced black
  screens because the api-gateway's always-on FrameGrabber and the
  browser's WHEP reader both contend for the same publisher's frames.
  The fix would be a separate ffmpeg fanout path (e.g. `eb226-display`
  alongside `eb226`) so the two readers don't compete.

At `buffalo_l` on CPU (M5), the real-time pipeline tops out around
0.5-1 fps. The admin portal's `DetectionOverlay` smooths this with a
snap-then-lerp interpolator so boxes still feel responsive.

Face registration (student APK → CameraX → upload) uses the same model
server-side, so registered embeddings live in the same FAISS index and
identity resolves immediately without a separate reindex.

---

## Passive liveness / anti-spoofing (MiniFASNet)

Phones held up to the camera and printed photos used to pass identity
recognition cleanly — ArcFace doesn't know it's looking at pixels-of-a-
face vs. a real face. As of 2026-04-26 the realtime pipeline runs a
fused MiniFASNet (Silent-Face-Anti-Spoofing, Apache-2.0) check on every
detected bbox before recognition can commit, and any track flagged as
spoof is suppressed from attendance updates.

### Where it runs

The two MiniFASNet ONNX submodels (~1.7 MB each) live alongside the
buffalo_l static pack at `~/.insightface/models/minifasnet/` and are
loaded by the **ML sidecar** with `CoreMLExecutionProvider` — same
process that already serves SCRFD + ArcFace. The api-gateway in Docker
proxies its per-frame liveness calls via `RemoteLivenessModel` over
`host.docker.internal:8001/liveness`, mirroring the SCRFD/ArcFace path.

```
Docker api-gateway → POST /liveness (jpeg + bboxes) → sidecar
                                                       ↓
                                            MiniFASNetV2 (scale 2.7) +
                                            MiniFASNetV1SE (scale 4.0)
                                                       ↓
                                            fused softmax "real" prob
```

### Tunables (`backend/.env.onprem`)

```
LIVENESS_ENABLED=true                # Master flag — false skips gating
LIVENESS_REAL_THRESHOLD=0.5          # Fused real-prob below this = "spoof"
LIVENESS_SPOOF_CONSECUTIVE=2         # K consecutive spoof verdicts to suppress
LIVENESS_REAL_RECOVERY_FRAMES=3      # K consecutive real verdicts to un-suppress
LIVENESS_RECHECK_INTERVAL_S=5.0      # How often each track is re-probed
LIVENESS_MAX_PER_FRAME=10            # Per-frame budget cap
```

The K-of-N debounce (`SPOOF_CONSECUTIVE` + `REAL_RECOVERY_FRAMES`)
prevents a single noisy verdict from flipping a real student to spoof or
vice-versa. A new track is NOT pre-emptively marked spoof; only after
`SPOOF_CONSECUTIVE` confirmed verdicts does suppression flip on.

### One-time pack export

```bash
backend/venv/bin/pip install torch onnxscript            # ~700 MB, host venv only
LIVENESS_UPSTREAM_DIR=/tmp/silent-face-anti-spoofing \
    backend/venv/bin/python -m scripts.export_liveness_models
./scripts/stop-ml-sidecar.sh && ./scripts/start-ml-sidecar.sh
docker compose -f deploy/docker-compose.onprem.yml up -d --force-recreate api-gateway
```

The sidecar's `/health` will then report `liveness.loaded: true` and the
gateway lifespan logs `Liveness backend bound — pack=...`.

`docker compose restart` is **not** enough — env-file changes only get
re-read on `up`/`recreate`. Use `--force-recreate` after editing env vars.

### Failure policy

- **Pack missing → degraded (not fatal).** Sidecar reports
  `liveness.loaded=false`, gateway logs a warning and binds None for the
  liveness backend, the realtime tracker treats every track as
  liveness-unknown and recognition continues unimpeded.
- **Per-call failure (sidecar HTTP error) → frame skip.** Tracker logs
  once and proceeds. A flaky network blip never blanks the live overlay
  or freezes recognition.
- **Spoof verdict → recognition suppressed for this track.** WebSocket
  payload still emits the track with `liveness_state="spoof"`; admin
  overlay (`DetectionOverlay.tsx`) renders a red box with "Spoof
  detected" + percentage instead of an identity binding.

### Operator workflows

| Action | How |
|---|---|
| Check sidecar status | `curl -s http://127.0.0.1:8001/health \| jq '.liveness'` |
| Re-export ONNX pack | `LIVENESS_UPSTREAM_DIR=/tmp/silent-face-anti-spoofing backend/venv/bin/python -m scripts.export_liveness_models --force` |
| Toggle off in prod | `LIVENESS_ENABLED=false` in `.env.onprem` + `docker compose ... up -d --force-recreate api-gateway` |
| Tighten threshold | Raise `LIVENESS_REAL_THRESHOLD` (0.5 → 0.7) — more strict; will cause more false-spoofs on real but obscured faces |
| Loosen sensitivity | Raise `LIVENESS_SPOOF_CONSECUTIVE` (2 → 4) — needs more confirmation before suppressing |

### Known caveats

- **Classroom-distance faces are near the model's training floor**
  (~40–60 px). Single-frame accuracy degrades; the K-of-N debounce is
  what makes it usable in practice.
- **Per-track recheck cadence is 5 s** by default. A track that flips
  from real-person to phone-screen (or the reverse) takes up to
  `RECHECK_INTERVAL_S × max(SPOOF_CONSECUTIVE, REAL_RECOVERY_FRAMES)` to
  catch up — ~15 s worst case.
- **`docker compose restart` doesn't reload env files.** Always
  `up -d --force-recreate api-gateway` after editing `.env.onprem`.
- **The export uses `torch.onnx.export(..., dynamo=False)`** (legacy
  TorchScript exporter). The new dynamo-based default writes weights to
  a sidecar `.onnx.data` file via ONNX external-data format, which ORT
  refuses to load when the InferenceSession's path-validation collides
  with the external file lookup. The legacy exporter produces a single
  self-contained ~2 MB ONNX file per submodel.
- **`conv6_kernel` must match input size.** For 80x80 inputs (the deploy
  variant) it's `(5, 5)`, computed as `((H+15)//16, (W+15)//16)` per
  upstream `src/utility.py::get_kernel`. Default `(7, 7)` raises a
  `size mismatch for conv_6_dw.conv.weight` on state_dict load.

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

### ⚠️ DO NOT re-run `seed_data` on the on-prem Mac

`backend/scripts/seed_data.py` calls `_wipe_all()` first, which truncates
**every** table including `face_embeddings`, `face_registrations`, and
`enrollments`, and also deletes the FAISS index file
([seed_data.py:355-380](backend/scripts/seed_data.py#L355-L380)). The Mac
currently holds **real registered student faces** that took multi-angle
captures from the student APK to produce. Running the seed against this
DB destroys all of them — students would have to re-register from
scratch, and any historical attendance/presence records lose their FK
anchor.

The on-prem stack is a **steady-state** environment now. Treat re-seed
as the same blast radius as `DROP DATABASE`. If you genuinely need to
add a new schedule or room, write a one-off ad-hoc SQL/script that
`INSERT`s the row instead of running the full seed.

Safe operations on the on-prem DB:

- Adding a new schedule: insert via the admin portal "Create Schedule"
  button, or run a targeted `INSERT INTO schedules ...` via psql.
- Adding a new room: same — admin portal, or `INSERT INTO rooms ...`.
- Adding faculty: admin portal Faculty page.
- Resetting an individual student's face: admin portal Student detail
  page → "Reset Face Registration" (preserves the user row + history).

If, despite all of the above, the Mac DB gets corrupted and a full
re-seed is unavoidable, the recovery path is:

1. `pg_dump` first so face data can be selectively restored if needed.
2. `docker exec iams-api-gateway-onprem python -m scripts.seed_data`.
3. Re-register every student's face manually via the student APK.

The VPS is different — it holds no face data, so re-seeding the VPS
postgres is a no-op for student PII:

```bash
# Re-seed VPS (faculty + schedules + rooms only — never student faces)
bash deploy/deploy.sh vps     # `deploy.sh` auto-re-runs seed_vps_minimal
```

The VPS seed (`seed_vps_minimal.py`) does NOT touch face_embeddings or
face_registrations because those tables don't exist on the VPS profile.

**If you add a new schedule to `SCHEDULE_DEFS` in `seed_data.py`**, do
NOT then re-seed on-prem. Either copy that schedule into the admin
portal manually on the Mac, or run a one-line `INSERT` via psql. The
constants file is now a reference for VPS seeds + fresh-clone first
boots, not a sync target.

---

## The big session-lifecycle auto-start/end

`backend/app/main.py` runs `session_lifecycle_check` every 15 seconds. It:

1. Pulls schedules whose `(day_of_week, start_time..end_time)` window
   contains `datetime.now()` and isn't already active → **auto-starts** a
   SessionPipeline for each (just attaches ML to the room's existing
   FrameGrabber — see "Always-on FrameGrabbers" below).
2. Pulls active sessions whose `end_time` is in the past → **auto-ends**
   them (tears down the SessionPipeline; FrameGrabbers stay alive for the
   process lifetime).

The rolling 30-min test schedules (`EB226-HHMM` / `EB227-HHMM`) use this
to exercise the full PRESENT / LATE / ABSENT / EARLY_LEAVE state machine
all day. Real faculty schedules ride the same code path.

This means "click Start Session" in the admin portal is usually
**unnecessary**: once the schedule window opens, the session appears by
itself. The button exists for (a) manual sessions outside the normal
window, (b) restart recovery, (c) explicit demo control.

### ML Sidecar — native CoreML/ANE inference

The api-gateway runs in a Linux Docker container; ONNX Runtime there
only ships with `CPUExecutionProvider`, so the M5's Apple Neural Engine
and Metal GPU can't be reached from inside Docker. The `ml-sidecar` is a
small native macOS Python process (no Docker) that loads the same
`buffalo_l_static` model pack with `CoreMLExecutionProvider` available,
exposes `/detect` and `/embed` HTTP endpoints, and serves them on
`127.0.0.1:8001`.

Architecture:

```
  Docker container (Linux)              Mac host (native macOS)
┌────────────────────────────┐         ┌───────────────────────────┐
│ iams-api-gateway-onprem    │         │ ml-sidecar                │
│  ├─ FrameGrabber (RTSP)    │         │  ├─ FastAPI (uvicorn)     │
│  ├─ ByteTrack              │  HTTP   │  ├─ InsightFace via ORT   │
│  ├─ FAISS index            │ ──────▶ │  │   with CoreML EP       │
│  ├─ DB + WS + APScheduler  │  loop-  │  └─ Endpoints:            │
│  ├─ RealtimeTracker        │  back   │      /detect (SCRFD)      │
│  └─ Calls sidecar via      │         │      /embed  (ArcFace)    │
│     RemoteInsightFaceModel │         │      /health              │
└────────────────────────────┘         └───────────────────────────┘
   :8000 (api)  →  host.docker.internal:8001
```

Files:

| File | Role |
|---|---|
| [backend/ml-sidecar/main.py](backend/ml-sidecar/main.py) | The FastAPI app. Loads InsightFace, exposes `/detect`, `/embed`, `/health`. ~250 lines. |
| [backend/app/services/ml/remote_insightface_model.py](backend/app/services/ml/remote_insightface_model.py) | Gateway-side proxy. Same `detect()` / `embed_from_kps()` API as in-process model; calls sidecar via httpx. |
| [backend/app/services/ml/inference.py](backend/app/services/ml/inference.py) | Selector. `set_realtime_model()` / `get_realtime_model()`. Bound once at gateway startup. |
| [scripts/iams-ml-sidecar.sh](scripts/iams-ml-sidecar.sh) | Supervisor loop. Restarts uvicorn on crash (3s backoff). Trap-cleans on SIGTERM. |
| [scripts/start-ml-sidecar.sh](scripts/start-ml-sidecar.sh) | nohup+disown launcher with health-wait. Idempotent. |
| [scripts/stop-ml-sidecar.sh](scripts/stop-ml-sidecar.sh) | SIGTERM → SIGKILL + pattern-scan cleanup. |

The gateway's lifespan calls `RemoteInsightFaceModel.healthcheck()` once
at boot. If the sidecar reports `model_loaded=true`, the realtime path
proxies to it. Else the gateway logs a warning and binds the in-process
`InsightFaceModel` (CPU-only, today's behaviour pre-sidecar). This means
a missing sidecar **degrades to "no overlays during sessions" rather than
refusing to start.**

Verify the sidecar is delegating to CoreML/ANE:

```bash
curl -s http://127.0.0.1:8001/health | python3 -m json.tool
```

Look for `"providers": ["CoreMLExecutionProvider", ...]` per task. If the
list shows only `CPUExecutionProvider`, the static-shape model export
hasn't been run on the host — see
[backend/scripts/export_static_models.py](backend/scripts/export_static_models.py)
and run `python -m scripts.export_static_models` from the host venv.

Logs: `~/Library/Logs/iams-ml-sidecar.log` (same convention as cam-relay).

### Always-on FrameGrabbers, session-gated ML

Strict session-gated policy: ML detection + recognition only run while a
real session is active. When no schedule is in its window, the live page
shows raw WHEP video with no overlays — no preview pipeline is spawned,
no recognition events fire, the FAISS path is idle.

To make the transition into a session feel instant despite that gating,
the backend pre-warms the slow parts at boot:

1. **InsightFace JIT** — one synthetic SCRFD pass right after model load
   (`insightface_model.warmup()` in [backend/app/services/ml/insightface_model.py](backend/app/services/ml/insightface_model.py))
   so the first real inference doesn't pay the ~3-5 s ONNX Runtime warmup
   tax.
2. **FrameGrabbers** — at startup, [backend/app/main.py](backend/app/main.py)
   opens an ffmpeg-backed `FrameGrabber` for every `Room` whose
   `camera_endpoint` is non-null. These RTSP readers stay alive for the
   lifetime of the process. Idle CPU is roughly 10-15 % on the M5 for
   two H.264 main streams decoding to drop frames; in exchange, the
   first frame delivered to a session pipeline lands in <1 s instead of
   waiting for the I-frame handshake.

When a session opens, the lifecycle scheduler attaches a SessionPipeline
to the existing grabber and ML starts producing bounding boxes
immediately. When the session ends, only the pipeline is torn down — the
grabber keeps running, ready for the next session in that room.

Caveat: changing a room's `camera_endpoint` in the DB requires a backend
restart to take effect. The boot-time preload reads each room's URL once
and never re-checks. Acceptable since camera URLs don't change at runtime.

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
- **Admin Vite "504 Outdated Optimize Dep" + blank route.** Symptom: the
  browser console shows `GET .../node_modules/.vite/deps/<pkg>.js?v=<hash>
  net::ERR_ABORTED 504` and `Failed to fetch dynamically imported module`,
  the route renders blank, and a hard reload doesn't help. The running
  Vite dev server is serving a stale optimize-deps hash whose files are
  gone from disk. **A browser refresh cannot fix this — Vite itself must
  restart.** Ctrl+C the dev server, then `cd admin && npm run dev`.
- **Admin `npm run dev` fails: `Cannot find module @rollup/rollup-darwin-arm64`.**
  npm 11.9.0 on Node 25 has a bug with optional platform deps: it can
  silently drop the darwin-arm64 native module (sometimes after `npm
  rebuild`, which has been observed swapping it for linux-arm64 modules
  on a Mac host). The clean-reinstall fix from the rollup error message
  (`rm -rf node_modules package-lock.json && npm i`) works initially but
  `npm rebuild` may break it again. **One-liner recovery without
  reinstalling everything:**
  ```bash
  cd admin && npm install @rollup/rollup-darwin-arm64@4.60.2 --no-save --force
  ```
  Match the version to whatever is in `admin/node_modules/rollup/package.json`.
  Verify with `ls admin/node_modules/@rollup/` — should show only
  `rollup-darwin-arm64`, never any `rollup-linux-*` entries on a Mac.
  Permanent fix would be downgrading to Node 22 LTS; until then keep this
  recovery command handy.
- **Admin `node_modules/.bin/` directory missing after `npm install`.** Same
  Node 25 / npm 11.9.0 family of bugs occasionally skips creating the
  `.bin/` symlink directory entirely, so `npm run dev` errors with `sh:
  vite: command not found` even though `node_modules/vite/` exists. Fix:
  `cd admin && npm rebuild`. Caveat: `npm rebuild` can simultaneously
  break the rollup native module (see above), so verify
  `ls node_modules/@rollup/` after rebuilding and re-run the rollup
  one-liner if the linux modules reappeared.

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
