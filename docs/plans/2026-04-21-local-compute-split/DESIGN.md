# Local-Compute Split — Design

**Branch:** `feat/local-compute-split`
**Date:** 2026-04-21
**Author:** CJ Jutba + Claude
**Related:** [RUNBOOK.md](RUNBOOK.md) (operational steps) · [../../../memory/lessons.md](../../../memory/lessons.md) (2026-04-21 entries)

---

## Problem

Live testing of the all-on-VPS deployment showed unacceptable end-to-end lag in the faculty live feed. Diagnosis: the **RPi → VPS → RPi round-trip over a constrained school uplink** was the bottleneck, not the ML model or the mobile rendering. Every frame that needed recognition traveled over the internet twice:

```
Camera → RPi → (WAN upload) → VPS mediamtx → VPS backend
         ← (WAN download) ← VPS backend broadcasts tracks ←
```

Adviser recommendation: *"Use the cloud only for viewing and remote access; keep detection + recognition on the local side."*

## Constraints

- The only on-site compute available for the thesis is the user's **MacBook Pro M5** (24 GB RAM, 1 TB SSD, Apple Silicon), brought to school each day on the MikroTik-managed **IAMS-Net** WiFi.
- The Mac goes home every evening → **system is school-hours-only** (documented, defensible).
- Docker Desktop on Apple Silicon **cannot reach the Neural Engine or Metal** from inside containers — ML inference is CPU-only in this deployment.
- School networks typically block inbound from the internet → any VPS → LAN traffic must be LAN → VPS **push**, not VPS → LAN pull.
- The existing admin portal has **no live-video player** (historically mobile-only). Adding one is part of this split.
- Mobile already works against the VPS; we want to minimize churn on student / faculty account flows that aren't about the live feed.

## Target architecture

```
┌── On-Campus (IAMS-Net, MikroTik) ─────────────────────────────────┐
│                                                                    │
│  Reolink Camera (LAN RTSP)                                         │
│       │ single pull (main stream)                                  │
│       v                                                            │
│  RPi (FFmpeg `-c copy` relay, no ML)                               │
│       │ RTSP push → MAC_LAN_IP:8554/<streamKey>                    │
│       v                                                            │
│  MacBook Pro M5 (Docker, static DHCP on IAMS-Net)                  │
│    ├ mediamtx  — one ingress path per camera                       │
│    │   ├ WHEP (8889) → LAN admin portal (same Mac's nginx proxy)   │
│    │   ├ RTSP reader → api-gateway's frame-grabber                 │
│    │   └ runOnReady ffmpeg → VPS RTSP push (outbound, `-c copy`)   │
│    │                                                               │
│    ├ api-gateway (FastAPI, CPU-only): SCRFD + ByteTrack + ArcFace │
│    │   + FAISS. Broadcasts tracks on /api/v1/ws/attendance/{id}.   │
│    │                                                               │
│    ├ postgres + redis                                              │
│    │                                                               │
│    └ nginx (80):                                                   │
│          /                → admin portal static (SPA)              │
│          /api/            → api-gateway:8000                       │
│          /api/v1/ws/…     → api-gateway:8000 (Upgrade)             │
│          /whep/<key>/whep → mediamtx:8889                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ outbound RTSP push (no inbound hole)
                              v
┌── VPS 167.71.217.44 — relay-only ─────────────────────────────────┐
│                                                                    │
│  mediamtx (8554 ingress, 8889 WHEP egress) — one path per camera  │
│  coturn  (3478 / UDP 49152–49252) — NAT traversal for mobile      │
│  nginx   (80) — static APK, /health, stub /                       │
│  dozzle  (9999) — logs                                            │
│                                                                    │
│  (No api-gateway, no postgres, no redis.)                         │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ public WebRTC WHEP
          ┌───────────────────┴────────────────────┐
          v                                        v
  Android mobile app (plain viewer)        Any remote viewer
    — VPS WHEP only, no overlays           — same URL, no auth required
    — accounts, registration, history      (optional thesis demo)
      still work but hit the Mac backend
      via VPS-routed proxy? NO — directly
      at the Mac's nginx when on IAMS-Net
```

**Rule of thumb:**
- *LAN (Mac)* handles **state** (attendance DB, FAISS, sessions, WebSocket tracks, admin portal).
- *Cloud (VPS)* handles **one thing**: rebroadcasting the public stream so off-campus viewers can still see the classroom.

## Key decisions

### 1. One camera pull, two mediamtx paths

The RPi pulls the camera once and pushes to the Mac's mediamtx. The Mac serves:
- a **local WHEP endpoint** (for the admin portal) at `http://<MAC_IP>/whep/<streamKey>/whep` (via nginx proxy), and
- a **public copy** pushed outbound to the VPS via mediamtx's `runOnReady` + `ffmpeg -c copy`, reachable at `http://167.71.217.44:8889/<streamKey>/whep`.

Why not two independent RPi pulls? Doubles camera-side RTSP load and RPi CPU for no benefit — the same mediamtx path can fan out to multiple readers.

Why push outbound instead of VPS pulling? **School NAT blocks inbound.** Outbound always works. Confirmed as a recurring theme in [../../../memory/lessons.md](../../../memory/lessons.md) (2026-04-21 entry: *"NAT-aware streaming — always push LAN → cloud, never pull"*).

### 2. Mobile live-feed video comes from the VPS, even in onprem mode

The Android app has two host fields in BuildConfig after this split:
- `BACKEND_HOST` — REST + WebSocket target. In onprem mode this is the Mac's LAN IP.
- `STREAM_HOST` — WebRTC video target. Always the VPS public relay IP, regardless of mode.

Why? The mobile user might be walking around the campus off IAMS-Net but still want to watch the stream. Routing video through the VPS lets the phone stream from anywhere with internet. Routing REST/WebSocket through the Mac requires IAMS-Net, which is fine for auth / registration / schedule (the thesis-scoped features).

### 3. Client-drawn overlays in the admin portal (not server-composited)

The admin portal's live-feed page plays raw WebRTC from the Mac's mediamtx and draws bounding boxes on an HTML canvas, fed by the existing `/api/v1/ws/attendance/{schedule_id}` WebSocket broadcast.

Alternative rejected: **server-side compositing** (backend draws boxes onto the frame and re-publishes). The 2026-03-17 design doc (`docs/plans/2026-03-17-rtsp-direct-compositing-plan.md`) explicitly listed this as a non-goal — server compositing adds 200–400 ms re-encode latency + 40–60% CPU per stream. Client-side is free, lower-latency, and the port from the existing Android `InterpolatedTrackOverlay.kt` is straightforward.

### 4. Third `switch-env.sh` mode: `onprem`

The script now has three modes: `local` (dev), `onprem` (prod on Mac), `production` (legacy VPS-everything). Same Supabase-key-preserving file mutator pattern as before. Reuses `detect_lan_ip()`.

Distinguishing `local` vs `onprem` in the `status` check: same host (Mac LAN IP) but port 8000 (bare api-gateway) vs port 80 (via nginx).

### 5. Mobile app scope changes

**Kept unchanged:** student + faculty login, registration, face capture (CameraX + ML Kit), schedule, history, profile, notifications.

**Stripped:** everything in the `FacultyLiveFeedScreen` that wasn't plain WebRTC — ML Kit on-device detection, `FaceIdentityMatcher` / `HybridFallbackController`, `HybridTrackOverlay` / `InterpolatedTrackOverlay`, `HybridDiagnosticHud`, `TimeSyncClient`, the attendance panel, session start/end controls, early-leave timeout slider.

The screen dropped from ~1400 lines to ~220 lines of plain Composable.

**Kept despite being on the original deletion list:** `AttendanceWebSocketClient.kt` — three other faculty screens (`FacultyClassDetailViewModel`, `FacultyLiveAttendanceViewModel`, `FacultyHomeViewModel`) still depend on it for their non-live-feed attendance displays. Deleting it would be a much larger refactor. Noted as a deviation from the plan; can be revisited later.

### 6. Admin portal gains a new live-feed route

`/schedules/:id/live` — entry point is a new "Watch Live" button on the existing schedule detail page. Route composes:
- [WhepPlayer.tsx](../../../admin/src/components/live-feed/WhepPlayer.tsx) — native `RTCPeerConnection` + SDP POST. Waits for ICE gathering COMPLETE before offer (mediamtx is non-trickle; see lessons 2026-03-21).
- [DetectionOverlay.tsx](../../../admin/src/components/live-feed/DetectionOverlay.tsx) — `<canvas>` with snap-then-lerp interpolation ported from Android `InterpolatedTrackOverlay.kt`.
- [AttendancePanel.tsx](../../../admin/src/components/live-feed/AttendancePanel.tsx) — present / late / early-leave / absent counts + per-status student lists.
- Session Start/End controls + early-leave timeout slider (moved from mobile).

No new npm dependencies — native `RTCPeerConnection`, `fetch`, `<canvas>`.

### 7. Deployment tooling: `deploy.sh relay` becomes the default

`bash deploy/deploy.sh relay` — new relay-only stack (mediamtx + coturn + nginx + dozzle). Just rsyncs the three relay configs and restarts.

`bash deploy/deploy.sh full` — legacy full stack preserved as fallback. The two stacks don't coexist (share port 80 / 8554), so the active script `docker compose down`s the other before starting.

## Non-goals

- Dedicated mini-PC procurement (noted as post-thesis recommendation).
- Off-campus mobile attendance marking — explicitly scoped out.
- Bidirectional DB sync between Mac postgres and any cloud postgres.
- Server-side video compositing (deliberately rejected).
- Running the backend natively outside Docker to reach CoreML EP — documented as a future option.
- Sidebar navigation entry for "Live Feed" — the plan originally called for it, but a duplicate link to `/schedules` wasn't valuable UX. Replaced with a contextual "Watch Live" button on the schedule detail page.

## Verification checklist

End-to-end happy path (after Phase 7 completion):

1. **Mode + config**
   - `./scripts/switch-env.sh status` reports `ONPREM (Mac LAN IP: <ip>:80 via nginx)`.
   - `git diff` on Android / admin configs shows the expected IP flip.

2. **Mac stack**
   - `./scripts/onprem-up.sh` brings up all 7 containers (postgres, redis, mediamtx, api-gateway, admin-build, nginx, dozzle).
   - `curl -fsS http://localhost/api/v1/health` returns `200`.
   - Admin portal loads at `http://<MAC_IP>/`.

3. **Stream chain**
   - RPi `.env` updated: `RELAY_HOST=<MAC_IP>` → relay restarts → RPi pushes to Mac mediamtx.
   - Mac mediamtx `runOnReady` ffmpeg starts → pushes to VPS mediamtx.
   - `docker exec iams-mediamtx-onprem curl -s http://localhost:9997/v3/paths/list` shows the pushed path locally.
   - `ssh root@167.71.217.44 'docker exec iams-mediamtx curl -s http://localhost:9997/v3/paths/list'` shows the re-published path.

4. **Admin portal live feed**
   - Open `/schedules/<id>/live` in a LAN browser — video plays within 2 s.
   - Start a session → bounding boxes appear with names as recognized faces enter frame.
   - Face-enter → box-appears latency **< 1.5 s** (stopwatch vs. visible clock in frame).

5. **Mobile app**
   - `cd android && ./gradlew clean installDebug` succeeds.
   - Faculty live feed → plain video from VPS, no overlays. No crashes on rotate / fullscreen / back.
   - Student registration still works (multipart upload against Mac backend).

## Rollback

`git checkout feat/cloud-based && ./scripts/switch-env.sh production && bash deploy/deploy.sh full && cd android && ./gradlew clean installDebug` restores the old all-on-VPS deployment. This branch is safe to abandon — the VPS's `docker-compose.prod.yml` was untouched, and every new file on this branch is net-additive (except the Android hybrid-detection deletions, which revert cleanly via git).

## Future work

1. **Dedicated mini-PC** — any Intel/Ryzen box with 16+ GB RAM and Ubuntu can take over from the MacBook. The `onprem` compose is host-agnostic; only the MikroTik DHCP reservation changes.
2. **Live Feeds index page** — a monitoring-group sidebar entry that lists currently-active schedules with one-click live links. Nice UX upgrade, left out to keep Phase 5 scoped.
3. **Native ML inference** — if the thesis ever needs higher fps, running the backend natively (outside Docker) on the M5 with onnxruntime CoreML EP unlocks Neural Engine acceleration. Diverges from VPS parity — weigh the tradeoff.
4. **GPU acceleration** — on a dedicated Linux mini-PC with NVIDIA, flipping `USE_GPU=true` + uncommenting the GPU deploy stanza in the compose file adds onnxruntime-gpu for ~3× throughput.
5. **Mobile off-campus scope** — if students need to view history / register from home, add a thin VPS-side read-only mirror of the Mac's postgres. Non-trivial (data consistency, security); out of scope here.
