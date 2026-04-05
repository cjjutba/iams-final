# Edge-to-Cloud WebRTC Live Streaming

**Date:** 2026-03-12
**Status:** Approved
**Goal:** Enable real-time live camera feed in the mobile app when the backend runs on a cloud VPS, accessible from any network.

## Problem

The backend is deployed on a DigitalOcean VPS (Singapore). The camera is on the local network in the Philippines. The VPS cannot reach the camera's RTSP stream directly, so the faculty live feed screen shows "Failed to open camera stream."

## Solution

The RPi edge device pushes the camera's RTSP sub-stream to the VPS via FFmpeg (`-c copy`, no transcoding). The VPS runs mediamtx which receives the stream and serves it to the mobile app via WebRTC (WHEP protocol). Detection metadata flows via the existing WebSocket.

## Architecture

```
Camera (Reolink P340, RTSP sub-stream 640x360 @ 15 FPS)
  ↓ RTSP (LAN)
RPi Edge Device
  ├→ MediaPipe face detection (existing, unchanged)
  └→ FFmpeg RTSP push (-c copy, no transcoding)
       ↓ RTSP over internet (~500 Kbps)
VPS (167.71.217.44)
  ├→ mediamtx (receives RTSP, serves WebRTC via WHEP)
  └→ FastAPI backend
       ├→ WebSocket /stream/{scheduleId} → detection metadata
       └→ POST /webrtc/{scheduleId}/offer → SDP signaling proxy
            ↓ WebRTC (~200-400ms latency)
Mobile App (faculty only)
  ├→ react-native-webrtc (video playback)
  └→ DetectionOverlay (bounding boxes from WebSocket)
```

## Component Changes

### 1. Edge Device (RPi) — new `stream_relay.py` module

- When a session is active, spawns FFmpeg to push camera RTSP sub-stream to VPS mediamtx
- Command: `ffmpeg -i rtsp://camera/sub -c copy -f rtsp rtsp://167.71.217.44:8554/room-{room_id}`
- Starts/stops alongside the existing scan loop (session-aware)
- Auto-reconnects if FFmpeg process dies (5s retry delay)
- Configurable via env vars: `STREAM_RELAY_ENABLED`, `STREAM_RELAY_URL`

### 2. VPS Docker — add mediamtx sidecar

- Add mediamtx container to `docker-compose.prod.yml`
- Expose port 8554 (RTSP ingest from RPi) and 8889 (WHEP for WebRTC)
- mediamtx config: accept RTSP publish, serve WebRTC
- Update nginx to proxy `/api/v1/webrtc/` WHEP requests to mediamtx
- Update UFW firewall to allow port 8554

### 3. Backend — minimal config changes

- Update `.env.production`: `USE_WEBRTC_STREAMING=true`
- Existing code handles everything:
  - `live_stream.py` sends `mode: "webrtc"` in connected message
  - `webrtc_service.py` proxies WHEP offers to mediamtx
  - `mediamtx_service.py` manages mediamtx lifecycle (may need adjustment for external container)

### 4. Mobile App — no changes needed

- `useDetectionWebSocket` already parses `mode: "webrtc"`
- `useWebRTC` already handles WebRTC signaling
- `FacultyLiveFeedScreen` already renders WebRTC video + DetectionOverlay

## Session Lifecycle

| Event | RPi | VPS | Mobile |
|-------|-----|-----|--------|
| Faculty starts session | Edge starts FFmpeg push to VPS | mediamtx receives stream | — |
| Faculty opens live feed | — | WebSocket sends `mode: webrtc` | WebRTC handshake → video plays |
| Faculty closes live feed | — | — | WebRTC disconnects |
| Faculty ends session | Edge stops FFmpeg | mediamtx drops stream | — |

## Performance

| Component | Resource | Impact |
|-----------|----------|--------|
| RPi FFmpeg (`-c copy`) | ~2-3% CPU, 10MB RAM | Negligible alongside MediaPipe |
| RPi upload bandwidth | ~500 Kbps | 3-10% of typical home upload |
| VPS mediamtx | ~1-2% CPU, 20MB RAM | Minimal alongside FaceNet backend |
| VPS egress per viewer | ~500 Kbps | Well within 4 TB/mo included |
| Mobile WebRTC decode | Hardware GPU | Same as a video call |

## Error Handling

- **RPi FFmpeg dies:** Auto-restart with 5s delay
- **VPS mediamtx unreachable:** RPi retries every 10s; mobile shows "Connecting..."
- **No active stream:** Backend sends error via WebSocket; mobile shows "No active session"
- **Network interruption:** WebRTC auto-reconnects via existing exponential backoff in `useWebRTC`

## Latency

- Expected: ~200-400ms end-to-end
- Camera → RPi: ~10ms (LAN)
- RPi → VPS: ~60ms (Philippines → Singapore)
- VPS → Phone: ~60ms (Singapore → Philippines)
- WebRTC processing: ~100-200ms
