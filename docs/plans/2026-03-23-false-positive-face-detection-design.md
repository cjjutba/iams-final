# False Positive Face Detection Reduction — Design

**Date:** 2026-03-23
**Problem:** Bounding boxes appearing on non-face objects (posters, clocks, round objects, random patterns) on both the Android Live Feed and backend attendance results.
**Goal:** Eliminate false positive face detections while maintaining smooth 30fps real-time feel.

## Root Cause

- **ML Kit (Android):** `PERFORMANCE_MODE_FAST` with `minFaceSize=0.10`, no landmark detection, no confidence filtering — every detection is drawn regardless of quality.
- **Backend SCRFD:** `det_thresh=0.3` is unnecessarily low; the attendance engine already filters at 0.5, but low-confidence detections still enter the pipeline and get broadcast as "Unknown" via WebSocket.

## Approach: Landmark Filtering + Static Suppression + Threshold Tightening

### 1. ML Kit Landmark Filtering (Android)

**File:** `android/app/webrtc/MlKitFrameSink.kt`

- Enable `LANDMARK_MODE_ALL` in FaceDetectorOptions
- Increase `minFaceSize` from `0.10f` → `0.13f`
- Post-detection filter: reject faces missing both eyes AND nose landmarks

```
For each detected face:
  - Must have at least LEFT_EYE or RIGHT_EYE landmark
  - Must have NOSE_BASE landmark
  - If both conditions fail → discard
```

**Rationale:** Real faces from CCTV angles almost always show at least one eye + nose. Objects, patterns, and pareidolia triggers lack these landmarks.

**Performance:** `LANDMARK_MODE_ALL` adds ~2-3ms per frame. At 30fps (33ms budget), still comfortable.

### 2. Aspect Ratio Validation (Android)

**File:** `android/app/webrtc/MlKitFrameSink.kt`

- Calculate `aspect_ratio = width / height` for each detection
- Valid range: `0.5` to `1.5`
- Outside range → discard

**Rationale:** Typical face ratio is ~0.77 (width:height). Tilted faces stretch to ~0.6–1.3. Anything outside 0.5–1.5 is not a face. Pure math, zero ML overhead.

### 3. Static Face Suppression (Android)

**File:** `android/app/webrtc/MlKitFrameSink.kt`

Track bbox center position over time per ML Kit tracking ID:

```
For each tracked face ID:
  - Store center positions over last 5 seconds (sample every 5th frame = ~30 data points)
  - Calculate max displacement from initial position
  - If max displacement < 2% of frame dimension for 5 consecutive seconds → suppress
  - If face starts moving again → immediately un-suppress
```

**Rationale:** Posters and photos have real facial landmarks but never move. Real students fidget even when sitting still (>2% displacement). 5-second window avoids false suppression of momentarily still students.

**Implementation:** One small ring buffer per tracked face ID. ML Kit tracking IDs persist across frames.

### 4. Backend SCRFD Threshold

**File:** `backend/app/config.py`

- Raise `INSIGHTFACE_DET_THRESH` from `0.3` → `0.5`

**Rationale:** Aligns model-level threshold with what the attendance engine already filters. Eliminates wasted processing on low-confidence detections that get discarded anyway. Fewer "Unknown" entries broadcast via WebSocket.

## Change Summary

| Layer | File | Change | Effect |
|-------|------|--------|--------|
| ML Kit config | `MlKitFrameSink.kt` | `LANDMARK_MODE_ALL`, `minFaceSize` 0.10→0.13 | Enables landmark data, cuts tiny detections |
| ML Kit filter | `MlKitFrameSink.kt` | Reject faces missing eye+nose landmarks | Kills objects, patterns, pareidolia |
| ML Kit filter | `MlKitFrameSink.kt` | Reject aspect ratio outside 0.5–1.5 | Kills elongated/wide false boxes |
| Static suppression | `MlKitFrameSink.kt` | Track position, suppress if <2% movement for 5s | Kills posters, photos on walls |
| Backend config | `config.py` | `INSIGHTFACE_DET_THRESH` 0.3→0.5 | Fewer false positives in recognition pipeline |

## Unchanged

- `HybridFaceOverlay.kt` — renders what ML Kit emits, no filtering changes needed
- `FaceCaptureView.kt` — registration already uses stricter minFaceSize (0.15)
- Recognition thresholds (ArcFace/FAISS 0.45 cosine, 0.1 margin) — already well-tuned
- 30fps target — all added filters are lightweight

## Lessons

- ML Kit `PERFORMANCE_MODE_FAST` with no landmark detection is too permissive for CCTV surveillance — it detects anything vaguely face-shaped. Always enable at least landmark mode for surveillance use cases.
- A low SCRFD det_thresh (0.3) is pointless when the consuming engine filters at 0.5 anyway — it just wastes compute and generates false "Unknown" broadcasts.
- Static object suppression via position tracking is the only reliable way to filter posters/photos that have genuine facial features.
