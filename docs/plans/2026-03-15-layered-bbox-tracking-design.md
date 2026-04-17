# Layered Bounding Box Tracking Design

**Date:** 2026-03-15
**Status:** Approved
**Goal:** Seamless, real-time bounding box tracking at 30 FPS over CCTV live stream with 50+ simultaneous faces

## Problem

The current system has a latency mismatch:
- RPi sends face detections at ~15 FPS via edge WebSocket (fast, but no identity)
- VPS runs ArcFace recognition at ~2 FPS (slow, but knows who the face is)
- Mobile overlay relies primarily on VPS recognition detections, resulting in choppy box movement

Bounding boxes need to move fluidly with faces in real-time, while identity information fills in asynchronously.

## Solution: Three-Tier Layered Pipeline

Each tier does what it's best at:

| Tier | Role | Rate |
|------|------|------|
| RPi | MediaPipe detection + lightweight centroid tracker (stable track IDs) | 15 FPS |
| VPS | Fuse edge tracks + ArcFace identity, Kalman-predicted unified tracks | 15 to 30 FPS upsampled |
| Mobile | Receive 30 FPS predicted boxes, spring animation to smooth remaining jitter | 30 FPS render |

### End-to-End Latency Target: ~35ms

```
Camera capture (0ms)
  -> MediaPipe detect (5ms)
  -> Centroid track (0.1ms)
  -> Network RPi->VPS (10-15ms)
  -> Kalman predict+update (0.05ms)
  -> Network VPS->Mobile (10-15ms)
  -> Spring animation start (1ms)
  -> GPU render
```

## Design Constraints

- 50+ simultaneous faces per camera view
- 30 FPS smooth box movement on mobile
- RPi stays lightweight (no heavy ML on edge for tracking)
- Battery-friendly on mobile (GPU-composited animation)
- Resilient to network drops at any tier

---

## Section 1: RPi Edge Layer — Centroid Tracker

### What It Does

Adds a lightweight centroid tracker to the existing MediaPipe detection loop. Instead of sending raw, unlinked bounding boxes each frame, the RPi assigns stable track IDs so the same face keeps the same ID across frames.

### Algorithm — Simple Centroid Tracker

1. Each frame, MediaPipe outputs N bounding boxes
2. Compute centroid (center x, y) of each box
3. Compare centroids to previous frame's centroids using Euclidean distance
4. Greedy nearest-neighbor matching — if distance < threshold (~50px at 640x480), same track
5. Unmatched detections get new track IDs
6. Tracks not seen for 5 consecutive frames get dropped

### Why Centroid and Not DeepSORT on RPi

- Centroid matching is ~0.1ms for 50 faces (just a distance matrix)
- No appearance features needed — camera is stationary, faces don't teleport
- DeepSORT would need a Re-ID CNN which would crush the RPi

### Enhanced Edge WebSocket Message

```json
{
  "type": "edge_detections",
  "room_id": "room-uuid",
  "timestamp": "2026-03-15T10:30:00.123Z",
  "frame_seq": 4521,
  "frame_width": 640,
  "frame_height": 480,
  "detections": [
    {
      "track_id": 7,
      "bbox": [120, 80, 90, 110],
      "confidence": 0.92,
      "centroid": [165, 135],
      "velocity": [2.1, -0.5]
    }
  ]
}
```

New fields:
- `frame_seq` — monotonic frame counter, lets VPS detect dropped frames
- `centroid` — center point (saves VPS from recalculating)
- `velocity` — pixels/frame movement vector (cheap to compute, helps VPS Kalman seed)

### CPU Impact

~1-2% additional on RPi 4. The centroid tracker is just array math, no neural nets.

### Files Changed

- `edge/app/detector.py` — Add `CentroidTracker` class
- `edge/app/edge_websocket.py` — Add `frame_seq`, `centroid`, `velocity` fields

---

## Section 2: VPS Fusion Layer — Kalman-Predicted Unified Tracks

### What It Does

Receives two streams — fast edge detections (15 FPS) and slow identity recognition (2 FPS) — and fuses them into a single, smooth, identity-enriched tracking stream at 30 FPS.

### Two Input Streams

| Source | Rate | Has Identity? | Has Bbox? |
|--------|------|---------------|-----------|
| RPi edge detections | 15 FPS | No | Yes (raw) |
| VPS ArcFace recognition | 2 FPS | Yes (user_id, name) | Yes (re-detected) |

### Fusion Architecture

```
RPi edge detections (15 FPS)
        |
  TrackFusionService
        ^
VPS recognition (2 FPS)
        |
  Kalman-predicted tracks (30 FPS) -> Mobile
```

### Per-Track State (One Kalman Filter Per Face)

```python
class FusedTrack:
    track_id: int              # Unified ID (mapped from edge track_id)
    edge_track_id: int         # Original RPi track ID
    user_id: str | None        # From recognition (None until identified)
    name: str | None           # Student name
    student_id: str | None     # Student number
    similarity: float | None   # Recognition confidence

    # Kalman state (constant-velocity model)
    state: [cx, cy, w, h, vx, vy, vw, vh]  # position + velocity
    covariance: 8x8 matrix

    last_edge_update: datetime
    last_recog_update: datetime
    missed_frames: int
    is_confirmed: bool         # Seen in 3+ frames
```

### Kalman Update Cycle

**On every edge detection (15 FPS):**
1. Predict — advance all Kalman filters by dt
2. Match — associate incoming edge detections to existing tracks by IoU + edge_track_id
3. Update — correct matched Kalman filters with observed bbox
4. Create/Delete — new tracks for unmatched detections, delete tracks missing 10+ consecutive frames

**On every recognition result (2 FPS):**
1. Match recognized face to existing fused track by bbox IoU
2. Update identity fields (user_id, name, similarity)
3. Identity is "sticky" — once assigned, stays until a better match or track dies

**On every 33ms tick (30 FPS output):**
1. Predict-only — advance all Kalman filters by 33ms without measurement
2. Package predicted bboxes + identities into message
3. Send to all connected mobile clients for this room

### Why Kalman on VPS, Not Mobile

- One Kalman instance per room on VPS vs. one per connected phone
- 50 faces x 8-state Kalman = trivial compute (~0.05ms per tick)
- If 10 students watch the same room, VPS computes once, sends to all
- Guarantees consistent smoothness across all devices

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| RPi WiFi drops for 2s | Kalman coasts for up to 3s, then fades tracks |
| Face briefly occluded | Track persists for 10 missed frames (~0.7s), Kalman coasts |
| Two faces cross paths | IoU + edge_track_id prevents ID swap |
| VPS recognition is slow | Boxes track via edge data, identity fills in when available |
| New face enters frame | Unidentified track immediately, identity within 0.5-1s |
| RPi track ID overflow | VPS maintains edge_track_id to fused_track_id map, handles remapping at 65535 |

### Files Changed

- `backend/app/services/track_fusion_service.py` — **New file**, Kalman filter + fusion logic
- `backend/app/services/edge_relay_service.py` — Route edge detections into TrackFusionService
- `backend/app/routers/live_stream.py` — Replace current detection push with fused_tracks output

---

## Section 3: Mobile Render Layer — Spring Animation Overlay

### What It Does

Receives pre-smoothed fused tracks at 30 FPS from the VPS and renders bounding boxes over the WebRTC video stream using GPU-accelerated spring animation.

### Architecture on Mobile

```
WebRTC Video (mediamtx)          WebSocket (fused_tracks, 30 FPS)
        |                                    |
   <RTCView />                     TrackAnimationEngine
        |                                    |
   +---------------------------------------------+
   |           DetectionOverlay (absolute)        |
   |  [Box1]  [Box2]  [Box3]  ... (50+)          |
   +---------------------------------------------+
```

### TrackAnimationEngine

Manages animated values per track:

```typescript
class TrackAnimationEngine {
  tracks: Map<number, {
    x: Animated.Value,
    y: Animated.Value,
    w: Animated.Value,
    h: Animated.Value,
    opacity: Animated.Value,
  }>
}
```

**On each `fused_tracks` message (30 FPS):**
1. Update existing tracks — spring-animate x/y/w/h to new values
2. Add new tracks — fade in opacity 0 to 1 (150ms)
3. Remove stale tracks — if track_id absent for 3 messages, fade out 1 to 0 (300ms), then remove

### Spring Animation Config

```typescript
Animated.spring(track.x, {
  toValue: newX,
  stiffness: 300,
  damping: 25,
  mass: 0.8,
  useNativeDriver: true,  // Runs on native UI thread
}).start();
```

`useNativeDriver: true` is critical — animation runs on the native UI thread, immune to JS thread GC pauses.

### 50+ Box Performance Optimizations

| Technique | Why |
|-----------|-----|
| `useNativeDriver: true` | All animation on native UI thread, zero JS bridge cost |
| `React.memo` per box | Only re-render component when track_id changes |
| Flat list of `Animated.View` | No nesting, no layout recalculation |
| Skip label for `missed_frames > 0` | Fewer text elements during occlusion |
| Pool animated values | Reuse from faded-out tracks instead of allocating new |

### Visual Design

- Green border (#22C55E) — Recognized student (has user_id)
- Amber border (#F59E0B) — Detected but not yet identified
- Fading opacity — Track coasting (missed_frames > 0) fades to 50%
- Label — First name + similarity %, positioned above box
- Border width — 2px (clean at 50+ boxes)

### Battery Impact

~5-8% additional drain vs. no overlay. Spring animations are GPU-composited. Comparable to a video call.

### Files Changed

- `mobile/src/engines/TrackAnimationEngine.ts` — **New file**, animated value management
- `mobile/src/components/DetectionOverlay.tsx` — Refactor to use TrackAnimationEngine with spring animation

---

## Section 4: Data Flow & Wire Protocol

### Full Pipeline

```
+------+    WS: edge_detections (15 FPS)     +------+
|      | ---------------------------------->  |      |
|  RPi |    RTSP: video stream (15-30 FPS)    |  VPS |
|      | ---------------------------------->  |      |
+------+                                      +------+
                                                  |
                                                  |  WS: fused_tracks (30 FPS)
                                                  v
                                              +------+
                                              |Mobile|
                                              +------+
                                                  ^
                                                  |  WebRTC: video (WHEP)
                                              +------+
                                              |media |
                                              | mtx  |
                                              +------+
```

### Message Formats

**1. RPi to VPS** (existing edge WS, enhanced):
```json
{
  "type": "edge_detections",
  "room_id": "room-uuid",
  "timestamp": "ISO8601",
  "frame_seq": 4521,
  "frame_width": 640,
  "frame_height": 480,
  "detections": [
    {
      "track_id": 7,
      "bbox": [120, 80, 90, 110],
      "confidence": 0.92,
      "centroid": [165, 135],
      "velocity": [2.1, -0.5]
    }
  ]
}
```
~200-500 bytes per message at 50 faces. At 15 FPS = ~7.5 KB/s upstream.

**2. VPS to Mobile** (fused_tracks, 30 FPS):
```json
{
  "type": "fused_tracks",
  "room_id": "room-uuid",
  "timestamp": "ISO8601",
  "seq": 89012,
  "frame_width": 640,
  "frame_height": 480,
  "tracks": [
    {
      "track_id": 7,
      "bbox": [121.3, 79.5, 90.2, 110.1],
      "confidence": 0.92,
      "user_id": "uuid-123",
      "name": "Juan Dela Cruz",
      "student_id": "22-00456",
      "similarity": 0.87,
      "state": "confirmed",
      "missed_frames": 0
    }
  ]
}
```
~500-800 bytes at 50 faces. At 30 FPS = ~24 KB/s per connected client.

**3. VPS to Mobile** (identity delta, sent only on change):
```json
{
  "type": "track_identity",
  "track_id": 7,
  "user_id": "uuid-123",
  "name": "Juan Dela Cruz",
  "student_id": "22-00456",
  "similarity": 0.87
}
```

### Bandwidth Budget

| Stream | Rate | Size |
|--------|------|------|
| RPi edge detections | 15 FPS | ~7.5 KB/s |
| VPS fused_tracks | 30 FPS | ~24 KB/s per client |
| Identity deltas | On change | Negligible |
| WebRTC video | 15-30 FPS | ~500 KB/s (H.264) |

Total per mobile client: ~525 KB/s. Well within 4G/WiFi capacity.

### MVP Bandwidth Optimization

Start with full JSON at 30 FPS. At 50 faces and ~24 KB/s, this is within WebSocket capacity. Future optimizations if needed:
- Send identity fields only in delta messages (~40% savings)
- Truncate floats to 1 decimal (~15% savings)
- Delta encoding for still faces (~50% fewer tracks per message)
- Binary format (MessagePack) (~30% savings vs JSON)

### Failure Modes & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| RPi WiFi drops | VPS: no edge_detections for 1s | Kalman coasts up to 3s, fades tracks |
| VPS overloaded | Mobile: seq gaps | Mobile coasts via spring animation inertia |
| Mobile backgrounded | App lifecycle event | Disconnect WS, reconnect on foreground, full state sync |
| RPi track ID collision | Track ID wraps at 65535 | VPS remaps via edge_track_id to fused_track_id map |

---

## Files Summary

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `edge/app/detector.py` | Modify | Add `CentroidTracker` class |
| `edge/app/edge_websocket.py` | Modify | Add frame_seq, centroid, velocity fields |
| `backend/app/services/track_fusion_service.py` | **New** | Kalman filter + fusion logic |
| `backend/app/services/edge_relay_service.py` | Modify | Route edge detections into TrackFusionService |
| `backend/app/routers/live_stream.py` | Modify | Output fused_tracks instead of raw detections |
| `mobile/src/engines/TrackAnimationEngine.ts` | **New** | Animated value management per track |
| `mobile/src/components/DetectionOverlay.tsx` | Modify | Refactor to use TrackAnimationEngine |

## Alternatives Considered

### A: Mobile-Heavy (Client-Side Prediction)
All prediction/interpolation on the phone. Rejected because 50+ Kalman filters per phone drains battery and varies by device quality.

### B: VPS-Heavy (Server-Side Only)
All tracking on VPS, mobile just renders. Rejected because without RPi centroid tracking, track ID stability suffers and VPS can't distinguish faces that cross paths without edge-side association.

### C: Layered Pipeline (Selected)
Distribute work across all three tiers. Each tier does what it's best at. RPi stays light, VPS does the smart fusion, mobile just animates.
