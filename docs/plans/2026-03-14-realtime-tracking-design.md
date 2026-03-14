# Real-Time Face Tracking — Hybrid Architecture Design

**Date:** 2026-03-14
**Status:** Approved

## Problem

The current architecture has a single recognition service on the VPS reading RTSP frames from mediamtx and producing both bounding boxes and identity labels. Since InsightFace takes 300-800ms per frame on CPU, bounding boxes arrive delayed relative to the WebRTC video the mobile app displays. This causes visible misalignment — boxes appear where faces *were*, not where they *are*.

## Solution: Approach A — RPi Real-Time Detection + VPS Async Recognition

Split detection and recognition into two independent channels:

| Channel | Source | Rate | Latency | Payload |
|---------|--------|------|---------|---------|
| **Video** | RPi → FFmpeg → mediamtx → WebRTC | 10 FPS | ~150ms | H.264 video |
| **Boxes** | RPi MediaPipe → WS → VPS relay → Mobile | 10 FPS | ~50ms | JSON bounding boxes |
| **Identity** | VPS InsightFace + FAISS | 2 FPS | async | user_id + name mapped to track_id |

Because the RPi reads the same RTSP source that feeds the video relay, bounding boxes are frame-aligned with the video by construction.

## Architecture Diagram

```
Reolink Camera (RTSP 896x512 @10fps)
        │
        ├──→ RPi MediaPipe (detection, ~20ms/frame)
        │        │
        │        ├──→ Face crops → HTTP POST /api/v1/face/process (every 500ms)
        │        │
        │        └──→ Bounding boxes → WebSocket → VPS EdgeRelayManager
        │                                              │
        │                                              └──→ Forwarded to Mobile WS clients
        │
        └──→ RPi FFmpeg -c copy → mediamtx (VPS)
                                      │
                                      └──→ WebRTC (WHEP) → Mobile video player

VPS Recognition Service (2 FPS):
  mediamtx RTSP → InsightFace → FAISS → identity_update → Mobile WS clients
```

## Component Changes

### 1. RPi Edge Device

**New file: `edge/app/edge_websocket.py`**
- Persistent WebSocket client connecting to `ws://VPS/api/v1/edge/ws?room_id=XXX`
- Sends `edge_detections` messages: `{ type, room_id, timestamp, detections: [{bbox, confidence, track_id}] }`
- Auto-reconnect with exponential backoff
- Runs in background thread, non-blocking

**Modified: `edge/app/main.py`**
- After MediaPipe detection, push bounding boxes to edge WebSocket (fire-and-forget)
- Continue sending face crops via HTTP POST as before

**Modified: `edge/app/config.py`**
- Add `EDGE_WS_URL` env var (default: derived from `BACKEND_URL`)

### 2. VPS Backend

**New file: `backend/app/services/edge_relay_service.py`**
- `EdgeRelayManager` singleton: receives edge boxes, fans out to mobile clients
- Per-room state: latest detections, connected mobile WebSocket set
- Thread-safe with asyncio locks

**New file: `backend/app/routers/edge_ws.py`**
- `GET /api/v1/edge/ws?room_id=XXX` — RPi connects here
- Validates room_id, registers with EdgeRelayManager
- On `edge_detections` message: stores + fans out to mobile clients

**Modified: `backend/app/routers/live_stream.py`**
- Mobile WebSocket now receives two message types:
  - `edge_detections` — real-time boxes from RPi (relayed)
  - `identity_update` — async identity mapping from recognition service
- On connect: register with EdgeRelayManager for the schedule's room

**Modified: `backend/app/config.py`**
- `RECOGNITION_FPS`: 15 → 2 (identity-only, no boxes needed)

### 3. Mobile App

**Modified: `useDetectionWebSocket.ts`**
- Handle `edge_detections`: update bounding boxes immediately (no delay queue)
- Handle `identity_update`: map `track_id → {user_id, name}` in identity cache
- Merge: apply cached identity to matching track_ids in current detections
- Remove detection delay queue (no longer needed — boxes are frame-aligned)

**Modified: `useDetectionTracker.ts`**
- When identity cache has a mapping for a track_id, persist that identity on the detection
- Existing IoU matching continues to work for frame-to-frame tracking

## Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| Box-to-video sync | 300-800ms behind | <50ms (frame-aligned) |
| Box update rate | ~2 FPS (recognition-limited) | 10 FPS (camera rate) |
| Identity resolution | Per-frame | Every 500ms (async) |
| RPi CPU usage | ~15% (MediaPipe) | ~18% (MediaPipe + WS send) |
| VPS CPU usage | ~80% (InsightFace @15fps) | ~30% (InsightFace @2fps) |

## Key Design Decisions

1. **RPi handles detection only** — MediaPipe runs at ~20ms/frame on RPi, well within budget
2. **VPS handles recognition only** — InsightFace at 2 FPS is sufficient for identity; reduces CPU from ~80% to ~30%
3. **WebSocket relay, not direct RPi→Mobile** — RPi is behind NAT; VPS acts as relay
4. **Track IDs bridge boxes and identity** — RPi assigns track_id per face; VPS recognition maps track_id → user_id; mobile merges them
5. **No delay queue needed** — Boxes come from same RTSP source as video relay, so they're inherently synchronized
