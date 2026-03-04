# Smooth 60 FPS Detection Overlay

**Date:** 2026-03-04
**Status:** Approved

## Problem

Bounding boxes update at 2 FPS (RECOGNITION_FPS=2.0), causing visible jumps/stutter over 30 FPS WebRTC video. Users expect smooth, real-time face tracking.

## Solution: Raise Backend FPS + Client-Side Interpolation

Two-pronged approach:
1. **Backend**: Increase recognition sampling from 2 FPS → 15 FPS (M5 MacBook Pro with CoreML handles this)
2. **Mobile**: Smoothly animate bounding boxes between detection updates using `react-native-reanimated` at 60 FPS on the native UI thread

## Architecture Flow

```
RTSP Camera (30 FPS)
    ├── mediamtx → WebRTC → Mobile VideoView (30 FPS video)
    └── Recognition Service (15 FPS sampling)
            → InsightFace detect+embed → FAISS match
            → WebSocket push (15 Hz)
                → Mobile receives detections
                    → IoU tracker assigns stable track IDs
                    → Reanimated interpolates bbox at 60 FPS
                        → Smooth overlay on top of video
```

## Backend Changes

### config.py
- `RECOGNITION_FPS`: 2.0 → 15.0

### live_stream.py (both HLS and WebRTC modes)
- `poll_interval`: 0.100 (10 Hz) → 0.066 (15 Hz)

No other backend changes needed. The recognition loop already handles variable FPS via its throttle mechanism.

## Mobile Changes

### New: `useDetectionTracker` hook
Assigns stable track IDs to detections across frames using IoU matching:
- Each detection gets a `trackId` (either `user_id` for known faces, or a generated ID for unknowns)
- On new frame: compute IoU between previous and current bounding boxes
- IoU > 0.3 → same face, reuse trackId → enables smooth animation
- No match → new face, appear immediately
- Previous trackId gone → fade out over 150ms

### Rewrite: `DetectionOverlay.tsx`
Replace static `View` positioning with `react-native-reanimated` animated styles:
- Each tracked face has 4 shared values: x, y, width, height
- On detection update → `withTiming(newValue, { duration: 80 })` for smooth transition
- Reanimated runs on native UI thread at 60 FPS — zero JS bridge overhead
- Label and border styling remain unchanged

### Dependency
- `react-native-reanimated` (likely already installed for navigation transitions)

## Performance Budget

| Component | Time | FPS Equivalent |
|-----------|------|----------------|
| InsightFace SCRFD+ArcFace (M5 CoreML) | ~50-70ms/frame | 14-20 FPS |
| FAISS search per face | ~1-2ms | negligible |
| WebSocket push | ~1ms | negligible |
| Mobile IoU matching | ~0.1ms | negligible |
| Reanimated interpolation | native thread | 60 FPS |

## Trade-offs

- **Interpolation lag**: On sudden head movements, boxes "catch up" over ~80ms. Acceptable for monitoring use case.
- **CPU usage**: 15 FPS recognition uses ~7.5x more CPU than 2 FPS. M5 handles this easily; may need tuning on weaker hardware.
- **Unknown face tracking**: IoU-based matching is approximate. Closely spaced unknown faces may occasionally swap IDs. Acceptable since unknown faces have no label.
