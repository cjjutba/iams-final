# Ghost Bounding Box Elimination — Design Doc

**Date:** 2026-04-10
**Problem:** Bounding boxes persist on the live feed when a face is completely not visible — covered by another person, walked out of frame, or fully occluded. The box should vanish immediately.

## Root Cause Analysis

Three independent systems contribute to ghost boxes:

1. **Backend (SCRFD + ByteTrack):** `TRACK_LOST_TIMEOUT=2.0s` keeps lost tracks alive for 20 frames. `track_activation_threshold=0.1` lets marginal detections revive tracks. SCRFD at `det_thresh=0.5` can detect partially visible faces.

2. **ML Kit (on-device):** Configured with `LANDMARK_MODE_NONE` — no way to verify facial features are actually visible. `isValidFace()` only checks aspect ratio. ML Kit reports face-shaped blobs even when the face is fully covered.

3. **Overlay (HybridFaceOverlay):** No staleness timeout. If data sources send stale data or stall, boxes persist indefinitely.

## Approach: Multi-Layer Defense (Approach B)

Fix at every layer where ghost boxes can leak through. Each layer is independently testable and provides defense in depth.

## Layer 1: Backend — ByteTrack Tuning & Detection Filtering

### Config changes (`backend/app/config.py`)

| Setting | Before | After | Rationale |
|---------|--------|-------|-----------|
| `TRACK_LOST_TIMEOUT` | 2.0s | 0.5s | Lost tracks die in 5 frames instead of 20. Sub-second occlusions still survive. |
| `track_activation_threshold` | 0.1 | 0.25 | Reject weakest false positives while keeping real faces (SCRFD scores real faces 0.5+). |

### Code changes (`backend/app/services/realtime_tracker.py`)

- Add minimum face size filter before ByteTrack: discard faces < 1% of frame area.
- SCRFD `det_thresh` stays at 0.5 (shared with registration quality gating).

## Layer 2: ML Kit — Landmark-Based Face Quality Gate

### Changes (`android/.../webrtc/MlKitFrameSink.kt`)

**FaceDetectorOptions:**
- `LANDMARK_MODE_NONE` → `LANDMARK_MODE_ALL`
- `minFaceSize`: 0.13f → 0.15f
- Keep `PERFORMANCE_MODE_FAST` (~1-2ms overhead for landmarks, negligible)

**Enhanced `isValidFace()`:**
- Keep existing aspect ratio check (0.5–1.5)
- Add: require at least both eyes and nose landmarks present
- Covered faces → ML Kit can't locate landmarks → face filtered out
- Partially turned faces → still have 1+ eye and nose → pass filter

## Layer 3: Overlay — Staleness Safety Net

### Changes (`android/.../ui/components/HybridFaceOverlay.kt`)

- Add `lastUpdatedAt` timestamp to `AnimatedFaceState`
- Add periodic sweep (`LaunchedEffect` with ~200ms interval): any track not refreshed in >500ms gets faded out and removed
- 500ms = 5 missed frames at 10fps broadcast rate. If no update in 5 frames, the face is gone or the pipeline stalled.
- Existing immediate-removal behavior (line 70-71) is unchanged — this is an additional safety net.

## Files Changed

| File | Change |
|------|--------|
| `backend/app/config.py` | `TRACK_LOST_TIMEOUT` 2.0→0.5, document `track_activation_threshold` |
| `backend/app/services/realtime_tracker.py` | `track_activation_threshold` 0.1→0.25, add min face size filter |
| `android/.../webrtc/MlKitFrameSink.kt` | Enable landmarks, enhance `isValidFace()` |
| `android/.../ui/components/HybridFaceOverlay.kt` | Add staleness timeout (500ms) with fade-out |

## What's NOT Changing

- SCRFD `det_thresh` (0.5) — shared with registration, side effects
- WebSocket protocol — current "absence = removal" pattern works correctly
- `PROCESSING_FPS` (10fps) — unrelated to ghost boxes
- Recognition thresholds — this is a display/tracking issue, not recognition

## Lessons

- ByteTrack's `track_activation_threshold=0.1` was far too low — it accepted nearly any detection as a valid track. Should default to 0.25+ for face tracking.
- ML Kit with `LANDMARK_MODE_NONE` has no way to distinguish "face visible" from "face-shaped blob." Always enable landmarks when face visibility matters.
- Display-layer staleness timeouts are essential safety nets for real-time pipelines — even if upstream is correct, network jitter or frame drops can cause stale displays.
