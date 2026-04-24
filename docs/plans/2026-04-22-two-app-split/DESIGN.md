# Two-App Split — Design

**Branch:** `feat/local-compute-split`
**Date:** 2026-04-22
**Builds on:** `docs/plans/2026-04-21-local-compute-split/DESIGN.md`

---

## Problem

The 2026-04-21 local-compute-split moved the backend + ML to the on-prem Mac and demoted the VPS to a video relay. That branch shipped a single Android APK (`com.iams.app`) containing both student and faculty screens, with REST + WebSocket pinned to LOCAL (Mac on IAMS-Net).

Two issues with that:

1. **Faculty can't watch from anywhere.** A pure-LOCAL APK only works on IAMS-Net. The whole point of having faculty in the app is that they can pull up the camera mid-day from another building, the office, home — anywhere with internet. Pinning their app to a Mac on a school WiFi defeats it.
2. **The single APK ships the union of both roles' deps.** ~16 MiB of CameraX + ML Kit + ExoPlayer that faculty don't need; ~6 MiB of WebRTC libs that students don't need.

## Constraints (carried forward + new)

- VPS still cannot run the ML stack at production fps (the original problem that motivated the on-prem split). Recognition still has to live on the Mac.
- Student face registration + face-recognition data must stay co-located with recognition (FAISS embeddings + `users` table FKs). Both live on LOCAL, so the student app's REST/WebSocket must point at LOCAL.
- Faculty must work off-campus → faculty app must auth + fetch schedules over the internet → there must be a thin API on the VPS.
- The faculty app needs to render the live stream from the VPS public mediamtx (post-2026-04-21 the VPS already does this).
- Existing faculty screens (analytics, alerts, manual entry, history, etc.) are not in scope for the new faculty app — those features are now admin-portal-only (web, on-prem only).

## Target architecture

```
┌── On-Campus (IAMS-Net) ───────────────────────────────────┐
│                                                            │
│  Reolink → RPi (FFmpeg copy)                               │
│       │ RTSP push → MAC_IP:8554/<key>                      │
│       v                                                    │
│  MacBook Pro M5 (Docker on IAMS-Net):                      │
│    ├ mediamtx — local WHEP + runOnReady push to VPS        │
│    ├ api-gateway (FULL ENABLE_*)                           │
│    ├ postgres + redis                                      │
│    └ nginx — admin portal + /api/ + /whep                  │
│                                                            │
│  Admin web (Mac LAN): full attendance monitoring           │
│  Student APK (com.iams.app.student):                       │
│      → http://MAC_IP/api/v1/*  (everything: face reg,      │
│        schedules, history, attendance review)              │
│                                                            │
└────────────────────────────────────────────────────────────┘
                            │
                            │ outbound RTSP push (-c copy)
                            v
┌── VPS 167.71.217.44 — thin API + relay ────────────────────┐
│                                                             │
│  mediamtx — accepts push, serves public WHEP                │
│  coturn   — TURN for off-campus phones                      │
│  api-gateway (THIN — ENABLE_ML=false + every router         │
│               that touches student data is OFF)             │
│  postgres — faculty users + schedules + rooms ONLY          │
│  nginx    — proxies /api/ to backend; /iams-faculty.apk     │
│                                                             │
│  Faculty APK (com.iams.app.faculty):                        │
│      → http://167.71.217.44/api/v1/auth/login               │
│      → http://167.71.217.44/api/v1/schedules/me             │
│      → http://167.71.217.44:8889/<key>/whep   (live video)  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key decisions

### 1. Two APKs, same codebase

`:app-student` (applicationId `com.iams.app.student`) and `:app-faculty` (applicationId `com.iams.app.faculty`) live in the same Gradle project. **Both keep the `com.iams.app` namespace** so existing imports (`com.iams.app.BuildConfig`, `com.iams.app.data.api.*`, etc.) work unmodified across both. Distinct `applicationId`s let them install side-by-side on a dev phone.

Decided NOT to create a separate `:core` library module: the duplication of shared files between the two app modules (auth screens, theme, components, NetworkModule) is small (~20 files) and keeping each app self-contained avoids cross-module Hilt + BuildConfig wiring that would need careful design. If shared-code drift becomes a real maintenance burden, promote to `:core` then.

### 2. Faculty app is pure viewer — 3 routes total

`FacultyRoutes`: LOGIN → SCHEDULES → LIVE_FEED.

Dropped from the faculty mobile experience (move to admin portal):
- Analytics dashboard, at-risk students, anomalies
- Alerts panel
- History / reports (PDF export)
- Manual attendance entry
- Class detail / student detail
- Live attendance roster (the WebSocket-driven side panel)
- Notifications
- Edit profile

These all still exist as backend endpoints + admin portal pages; faculty access them by walking to a workstation, not from their phone.

The faculty `FacultyLiveFeedScreen` is a minimal `NativeWebRtcVideoPlayer` + back button + fullscreen toggle. No detection overlays, no attendance panel, no session-start button, no early-leave timeout slider. The on-prem admin portal owns all of that.

### 3. Same backend image, ENABLE_* flags decide profile

[backend/app/config.py](../../../backend/app/config.py) gained 13 `ENABLE_*` settings. The VPS thin profile sets all heavy flags to `false`; the on-prem Mac runs everything. Always-on routers (`auth`, `users`, `schedules`, `rooms`, `health`) cover the faculty app's needs.

[backend/app/main.py](../../../backend/app/main.py) guards every flagged section in lifespan + every router include. The VPS container never imports `insightface`, `faiss`, or `redis` at runtime — those modules are only imported inside flag-gated blocks.

### 4. VPS DB is seeded minimal — no student PII on the cloud

[backend/scripts/seed_vps_minimal.py](../../../backend/scripts/seed_vps_minimal.py) imports the data constants from `seed_data.py` so changing a faculty name or adding a schedule is a one-line edit in one place. It seeds **only**: `faculty_records`, faculty `users`, admin user, `rooms`, real `schedules` (no rolling 30-min dev sessions), `system_settings`. Skips: students, face embeddings, enrollments, attendance records, presence logs.

### 5. switch-env.sh manages the student app only

The student app's BuildConfig keys are now `IAMS_STUDENT_BACKEND_HOST`/`PORT` (with the legacy `IAMS_BACKEND_*` kept as fallback). `switch-env.sh local|onprem|production` mutates only those. The faculty app's `IAMS_FACULTY_API_HOST`/`STREAM_HOST` keys are pinned to `167.71.217.44` in `gradle.properties` and never mutated. This makes "switch to local" mean exactly "point the student app at local Docker"; the faculty app is unaffected.

### 6. Three deploy modes on the VPS

`deploy/deploy.sh vps` (default) — thin API + video relay. The new normal.
`deploy/deploy.sh relay` — video-only fallback (thesis-demo / sanity check).
`deploy/deploy.sh full` — legacy pre-split fallback. Each mode tears down the others before starting itself.

## Non-goals

- Real-time local→VPS sync of schedules / users. Seed is the source of truth; admin portal edits to schedules don't propagate to VPS until a re-deploy.
- A `:core` library module (see decision 1).
- Hot-reloading the faculty APK without uninstalling the legacy `com.iams.app` APK first (different applicationId requires one-time uninstall of the legacy build).
- Push notifications on the faculty APK (dropped; surfaced in admin portal toasts when faculty are at the workstation).
- HTTPS on the VPS (HTTP is fine for thesis demo; certbot wiring deferred).

## Verification checklist

End-to-end after the cutover:

| # | Check | Expected |
|---|---|---|
| 1 | `./scripts/switch-env.sh status` | `ONPREM (Student app → Mac LAN IP: ...:80 via nginx)` + `Faculty app → VPS: 167.71.217.44:80 (fixed)` |
| 2 | `curl http://167.71.217.44/api/v1/health` | 200 OK; components shows `redis: disabled`, `faiss: disabled` |
| 3 | `curl -X POST http://167.71.217.44/api/v1/auth/login -d {faculty creds}` | 200 + JWT |
| 4 | `curl http://167.71.217.44/api/v1/face/register` | 404 (route disabled by flag) |
| 5 | `curl http://<MAC_IP>/api/v1/face/status` (logged in) | 200 (full backend on Mac) |
| 6 | `cd android && ./gradlew :app-student:assembleDebug` | Builds; APK ~60 MB |
| 7 | `cd android && ./gradlew :app-faculty:assembleDebug` | Builds; APK ~50 MB |
| 8 | Install both APKs side-by-side | "IAMS Student" + "IAMS Faculty" launchers visible |
| 9 | Faculty APK on cellular | login → schedules → live feed plays |
| 10 | Admin portal on Mac | start session, walk into frame, see boxes within 1.5 s |

## Rollback

```bash
# Step 1: roll the VPS back to legacy full stack.
bash deploy/deploy.sh full

# Step 2: roll the Android workspace back to the single-APK layout.
git checkout feat/cloud-based -- android/

# Step 3: rebuild & install legacy APK.
cd android && ./gradlew clean installDebug
```

The single APK is preserved in `feat/cloud-based`'s git history. The VPS's full-stack container images are preserved in DigitalOcean container storage.

## Lessons

- **Reified Hilt navigation start-decisions need a tiny ViewModel.** Composables can't `@Inject` directly; the pattern is a 4-line `@HiltViewModel class NavStartViewModel(val tokenManager: TokenManager) : ViewModel()` consumed via `hiltViewModel()`. Worked cleanly for `FacultyNavHost`'s LOGIN-vs-SCHEDULES decision.
- **Don't try to factor a `:core` library mid-refactor.** With Hilt SingletonComponent + per-app `BuildConfig` values, a library module needs run-time injection of the BuildConfig fields — non-trivial. Two self-contained app modules with shared file copies is the pragmatic path; only escalate if the duplication actually rots.
- **Sentinel exception is the cheap way to wrap an existing 400-line `try:` block in a feature flag.** Re-indenting hundreds of lines is a recipe for whitespace bugs; raising `_SkipBackgroundJobs` from inside the try gets the same behavior with a 4-line diff.
- **`namespace` and `applicationId` are independent.** Reusing the same `namespace` across two app modules keeps `com.iams.app.BuildConfig` resolvable from shared source files without per-app import rewrites; distinct `applicationId`s give each app a unique install ID.
