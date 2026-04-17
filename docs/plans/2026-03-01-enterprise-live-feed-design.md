# Enterprise Live Feed — Design Document

**Date:** 2026-03-01
**Status:** Approved — Implementing
**Scope:** Enhance existing IAMS HLS + recognition pipeline to enterprise-grade, production-ready, scalable to 50+ simultaneous students.

---

## Problem Statement

The existing pipeline is architecturally correct but has five specific bottlenecks that prevent enterprise/production readiness:

| # | Gap | Impact |
|---|-----|--------|
| 1 | `RECOGNITION_MAX_BATCH_SIZE: 20` hard cap | Only 20 faces processed per frame; 50+ students means dropped faces |
| 2 | HLS: 1s segments, 2-segment playlist (3-6s latency) | Video feels laggy; detection boxes visibly lag behind action |
| 3 | `_name_cache` is a plain module-level dict | Race condition under concurrent rooms / threads writing cache simultaneously |
| 4 | RTSP reconnect: fixed `time.sleep(2.0)` | Under network instability, floods reconnect attempts; no backoff |
| 5 | Mobile reconnect: fixed 3s delay | Same issue; app hammers the server on repeated failures |

---

## Architecture (unchanged — enhanced)

```
Camera (RTSP H.264)
       │
       ├──► FFmpeg (HLS) ─────────────────────────► .m3u8 + .ts ──► Mobile HLS Player
       │    0.5s segments, 3-segment window                               │
       │    ≈ 1.5-2.5s end-to-end latency                                │
       │                                                                  │ (video)
       └──► Recognition Loop ─────────────────────► WebSocket ────► Overlay Layer
            8 FPS, batch 50 faces                   ~200 bytes/msg   (SVG boxes + names)
            FaceNet GPU batch → FAISS                                      │
                                                                           ▼
                                                                    Attendance Sidebar
```

**Key principle:** Video and metadata travel independently. The overlay is synced visually because both streams run at the same FPS/latency. No timestamp sync needed — boxes update at 8Hz which feels instantaneous.

---

## Changes Required

### Backend

#### 1. `backend/app/config.py`
- `RECOGNITION_MAX_BATCH_SIZE`: 20 → 50
- `HLS_SEGMENT_DURATION`: 1 → 0.5 (float, seconds per segment)
- `HLS_PLAYLIST_SIZE`: 2 → 3 (3 × 0.5s = 1.5s sliding window)
- `RECOGNITION_FPS`: 8.0 → 10.0 (faster detection updates)
- `HLS_USE_FMPEG4`: new bool flag for fMP4 segments

#### 2. `backend/app/services/hls_service.py`
- Reduce segment duration to 0.5s (matches new config)
- Add `-hls_segment_type fmp4` + `-hls_fmp4_init_filename init.mp4` for fMP4
- Keep `-c:v copy` (zero transcoding)
- Serve `init.mp4` via the existing segment endpoint (already handles any filename)
- Update `get_segment` to also allow `init.mp4`

#### 3. `backend/app/services/recognition_service.py`
- Remove the `face_crops[:max_batch]` slice cap — or raise cap to 50
- Replace `time.sleep(2.0)` in `_reconnect` with exponential backoff (2s, 4s, 8s, max 30s)
- Add per-state backoff counter that resets on success

#### 4. `backend/app/routers/live_stream.py`
- Replace module-level `_name_cache: Dict` with a thread-safe `threading.Lock`-protected cache class
- Add TTL: cache entries expire after 5 minutes (re-query if student name changes)
- Raise poll interval from 125ms to 100ms (10Hz metadata push)

### Mobile

#### 5. `mobile/src/hooks/useDetectionWebSocket.ts`
- Replace fixed 3s reconnect delay with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Reset backoff on successful connection

#### 6. `mobile/src/components/video/DetectionOverlay.tsx`
- Use stable `user_id` or position hash as React key (already does this — verify no recreation on update)
- Add "unknown" face count badge when `user_id === null`
- Thicker border (2px → 3px), improved label contrast (white text on dark background)
- Add pulsing animation for newly-detected faces

#### 7. `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx`
- Add detection count badge to header ("12 detected")
- Add unknown face count indicator
- Show recognition FPS in status bar
- Improve empty state when no faces detected yet

---

## Non-Goals

- WebRTC (too complex, not needed for attendance use case)
- Multi-camera per room (1 RPi per room as decided)
- CDN distribution (single campus, local network)
- Server-side video annotation (adds transcoding overhead)

---

## Expected Outcomes

| Metric | Before | After |
|--------|--------|-------|
| Max faces per frame | 20 | 50+ |
| HLS end-to-end latency | 3-6s | 1.5-2.5s |
| RTSP reconnect behavior | Flood (fixed 2s) | Exponential backoff |
| Mobile reconnect | Fixed 3s | Exponential backoff |
| Name cache safety | Race-prone | Thread-safe with TTL |
| Detection update rate | 8Hz | 10Hz |
