# Smooth Real-Time Pipeline Design

**Date:** 2026-03-15
**Status:** Approved

## Problem

The current pipeline has significant bounding box delay:
- Recognition runs at 2 FPS (fixed polling), causing most boxes to show "Unknown"
- HLS adds 1.5s inherent delay, forcing a 1500ms artificial delay queue in the mobile app
- Multiple streaming modes (HLS/WebRTC/Legacy) add complexity and fallback logic
- Bounding boxes feel laggy and disconnected from the video

## Solution: WebRTC + Fast Detection + Event-Driven Recognition

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  LOCALHOST (MacBook) / PRODUCTION (RPi + VPS)           │
│                                                         │
│  ┌──────────────┐     RTSP      ┌──────────────┐       │
│  │ Camera Source │──────────────▶│  mediamtx    │       │
│  │ (webcam/RPi) │               │  (WebRTC)    │───────┼──▶ Mobile (video)
│  └──────┬───────┘               └──────────────┘       │
│         │ frames                                        │
│         ▼                                               │
│  ┌──────────────┐  detections    ┌─────────────┐       │
│  │  Detection   │──────────────▶│ Track Fusion │       │
│  │  (MediaPipe) │  (15-30 FPS)   │  (Kalman)   │───────┼──▶ Mobile (boxes via WS)
│  │  Edge/Local  │               │  (30 FPS)    │       │
│  └──────────────┘               └──────┬──────┘       │
│                                        │               │
│  ┌──────────────┐  identity_update     │               │
│  │ Recognition  │◀────────────────────┘               │
│  │ (InsightFace)│  (on new tracks only)                │
│  │  (async)     │─────────────────────────────────────┼──▶ Mobile (names via WS)
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

### Key Principles

1. **WebRTC only** — drop HLS entirely. Sub-300ms video latency via mediamtx WHEP.
2. **Fast detection drives bounding boxes** — MediaPipe at 15-30 FPS, smoothed to 30 FPS by Kalman filter.
3. **Recognition is async and event-driven** — only triggers on new/unidentified tracks, not every frame.
4. **Same mobile app code** for localhost and production — only the detection source differs.
5. **Client-side interpolation** — spring animations at 60 FPS between 30 FPS data updates.

## Localhost Camera Pipeline

Backend runs a `LocalCameraService` for development:
- Opens webcam via OpenCV at 30 FPS
- Runs MediaPipe face detection (~5ms per frame on MacBook)
- Pushes raw stream to mediamtx via RTSP (FFmpeg subprocess)
- Feeds detections into `track_fusion_service` (same path as edge WebSocket)

### Config Switching

```
# Localhost (.env)
CAMERA_SOURCE=0
STREAM_MODE=webrtc
DETECTION_SOURCE=local

# Production (.env)
CAMERA_SOURCE=rtsp://rpi:8554/cam
STREAM_MODE=webrtc
DETECTION_SOURCE=edge
```

### Localhost vs Production Differences

| Component | Localhost | Production |
|-----------|-----------|------------|
| Camera | MacBook webcam | RPi picamera |
| Detection | Backend (MediaPipe, 30 FPS) | RPi (MediaPipe, 15 FPS) |
| Stream push | Backend FFmpeg → mediamtx | RPi FFmpeg → mediamtx |
| Detection transport | In-process function call | WebSocket from RPi |

Everything else (track fusion, recognition, mobile app) is identical.

## Detection & Bounding Box Smoothness

Three layers produce smooth boxes:

### Layer 1: Fast Detection (15-30 FPS)
- MediaPipe on every frame with centroid-tracked IDs
- MacBook: 30 FPS (~5ms). RPi: 15 FPS (~30ms)

### Layer 2: Kalman Fusion (30 FPS output)
- Predicts positions between detections to fill gaps
- Smooths MediaPipe jitter
- Coasts through brief misses (1-3 frames) instead of boxes disappearing

### Layer 3: Client-Side Interpolation (60 FPS render)
- `react-native-reanimated` spring animations between WebSocket updates
- Boxes animate at display refresh rate

### Changes from Current Implementation
- Remove detection delay queue (no HLS compensation needed)
- Remove HLS fallback code
- Tune Kalman: lower process noise for smoother motion
- Send fused_tracks at consistent 30 FPS (predict-only frames when no new detection)

### Expected Result
- Video: 30 FPS via WebRTC, <300ms latency
- Bounding boxes: 30 FPS data, interpolated to 60 FPS
- Brief occlusions: box coasts ~300ms before fading out

## Event-Driven Recognition

Recognition triggers only when:
1. **New track appears** — face the tracker hasn't seen
2. **Unidentified track persists** — visible 1+ seconds, no identity yet (retry)
3. **Periodic re-verification** — every ~10 seconds for identified faces

### Flow
```
New track (no identity)
  → Crop face from latest frame
  → Queue for async recognition
  → InsightFace embedding + FAISS search (~300-500ms)
  → Match (similarity > 0.6): push identity_update
  → No match: retry after 1 second
```

### Benefits
- After initial identification (~15-30s), recognition is mostly idle
- No "Unknown" flickering — name fades in once recognized
- CPU freed for detection and streaming

## Mobile App Changes

### Remove
- HLS player and HLS fallback logic
- Detection delay queue (1500ms compensation)
- Legacy Base64 frame mode
- Mode negotiation/fallback chain

### Simplify to Three Message Types
```
"connected"     → stream URL, detection dimensions
"fused_tracks"  → [{bbox, track_id, name?, similarity?}]
"heartbeat"     → keep-alive
```

### Box Rendering
- No name yet → thin border box only
- Identified → fade in name label with confidence
- Track lost → box fades out over ~200ms

## Scope Summary

### Keep
- `track_fusion_service.py` — Kalman core, identity inheritance
- `recognition_service.py` — InsightFace + FAISS (refactor trigger logic)
- `edge_relay_service.py` — RPi WebSocket relay (production)
- `mediamtx.yml` — WebRTC/RTSP config
- RPi edge code — untouched
- `react-native-reanimated` animations

### Refactor
- `live_stream.py` — remove HLS/legacy, streamline to WebRTC + fused_tracks
- `recognition_service.py` — fixed 2 FPS → event-driven
- `useDetectionWebSocket.ts` — strip delay queue, HLS compensation, legacy handling
- `FacultyLiveFeedScreen.tsx` — remove HLS player, simplify to WebRTC + overlay

### Remove
- `hls_service.py` usage (keep file, don't invoke)
- HLS FFmpeg spawning in `live_stream.py`
- Detection delay queue in mobile
- Legacy Base64 frame handling
- Mode negotiation/fallback logic

### Add New
- `LocalCameraService` — webcam + MediaPipe + RTSP push (localhost dev)
- Config flag `DETECTION_SOURCE=local|edge`
