# Ghost Bounding Box Elimination — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate ghost/stale bounding boxes that persist on the live feed when a face is completely not visible (occluded, out of frame, covered).

**Architecture:** Multi-layer defense — fix at backend (ByteTrack tuning + face size filter), ML Kit (landmark-based quality gate), and overlay (staleness timeout). Each layer independently prevents ghost boxes.

**Tech Stack:** Python/FastAPI (backend), Kotlin/Jetpack Compose (Android), ML Kit Face Detection, ByteTrack (supervision), InsightFace SCRFD

**Design doc:** `docs/plans/2026-04-10-ghost-bbox-elimination-design.md`

---

## Task 1: Backend — Reduce TRACK_LOST_TIMEOUT

**Files:**
- Modify: `backend/app/config.py:91`

**Step 1: Change the config value**

In `backend/app/config.py`, change line 91:

```python
# Before:
TRACK_LOST_TIMEOUT: float = 2.0  # Seconds before removing lost track (shorter = less stale boxes)

# After:
TRACK_LOST_TIMEOUT: float = 0.5  # Seconds before removing lost track (5 frames at 10fps)
```

**Step 2: Verify no other code depends on the old value**

Run: `docker compose exec api-gateway grep -r "TRACK_LOST_TIMEOUT" app/`

Expected: Only `config.py` definition and `realtime_tracker.py` usage. No hardcoded "2.0" references.

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "fix: reduce TRACK_LOST_TIMEOUT from 2.0s to 0.5s to eliminate ghost boxes"
```

---

## Task 2: Backend — Raise track_activation_threshold

**Files:**
- Modify: `backend/app/services/realtime_tracker.py:98`

**Step 1: Change the threshold**

In `backend/app/services/realtime_tracker.py`, change line 98:

```python
# Before:
track_activation_threshold=0.1,

# After:
track_activation_threshold=0.25,
```

**Step 2: Rebuild and verify backend starts cleanly**

Run: `docker compose up -d --build api-gateway`
Run: `docker compose logs --since 30s api-gateway`

Expected: No errors. ByteTrack initializes with new threshold.

**Step 3: Commit**

```bash
git add backend/app/services/realtime_tracker.py
git commit -m "fix: raise ByteTrack track_activation_threshold from 0.1 to 0.25"
```

---

## Task 3: Backend — Add minimum face size filter

**Files:**
- Modify: `backend/app/services/realtime_tracker.py:140-158`

**Step 1: Add the filter**

In `backend/app/services/realtime_tracker.py`, after the existing NMS call (line 151) and before creating `det_array` (line 153), add a minimum face size filter. Replace lines 140-158 with:

```python
        # 2. Convert InsightFace results to supervision Detections
        bboxes = []
        confidences = []
        embeddings_list = []
        for face in raw_faces:
            x1, y1, x2, y2 = face.bbox.astype(float)
            bboxes.append([x1, y1, x2, y2])
            confidences.append(float(face.det_score))
            embeddings_list.append(face.normed_embedding.copy())

        # Apply NMS to remove duplicate face detections
        bboxes, confidences, embeddings_list = self._nms_faces(bboxes, confidences, embeddings_list)

        # Filter out tiny faces (< 1% of frame area) — likely false positives
        frame_area = self._frame_w * self._frame_h
        filtered = []
        for i, bbox in enumerate(bboxes):
            face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if face_area >= frame_area * 0.01:
                filtered.append(i)
        if filtered:
            bboxes = [bboxes[i] for i in filtered]
            confidences = [confidences[i] for i in filtered]
            embeddings_list = [embeddings_list[i] for i in filtered]
        else:
            # All faces were too small — treat as no detections
            self._expire_lost_tracks(now)
            duration_ms = (time.monotonic() - t0) * 1000.0
            return TrackFrame(
                tracks=[],
                fps=1000.0 / max(duration_ms, 0.1),
                processing_ms=duration_ms,
                timestamp=now,
            )

        det_array = np.array(bboxes, dtype=np.float32)
        conf_array = np.array(confidences, dtype=np.float32)

        detections = sv.Detections(
            xyxy=det_array,
            confidence=conf_array,
        )
```

**Step 2: Run existing tests**

Run: `docker compose exec api-gateway python -m pytest tests/ -q -k 'tracker'`

Expected: All existing tests pass (there are currently no tracker-specific tests, so this confirms no import errors).

**Step 3: Commit**

```bash
git add backend/app/services/realtime_tracker.py
git commit -m "fix: filter out faces smaller than 1% of frame area before tracking"
```

---

## Task 4: Android — Enable ML Kit landmarks and enhance face validation

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt:66-75` (FaceDetectorOptions)
- Modify: `android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt:207-215` (isValidFace)

**Step 1: Add FaceLandmark import**

At the top of the file (after line 10), add the landmark import:

```kotlin
import com.google.mlkit.vision.face.FaceLandmark
```

**Step 2: Update FaceDetectorOptions**

Replace lines 66-75:

```kotlin
    private val faceDetector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
            .setMinFaceSize(0.15f)
            .enableTracking()
            .build()
    )
```

Changes: `LANDMARK_MODE_NONE` → `LANDMARK_MODE_ALL`, `minFaceSize` 0.13f → 0.15f.

**Step 3: Update isValidFace to require key landmarks**

Replace lines 207-215:

```kotlin
    /**
     * Filters out false positive face detections.
     * Requires: reasonable aspect ratio AND at least both eyes + nose landmarks visible.
     * Covered/occluded faces won't have detectable landmarks → filtered out.
     */
    private fun isValidFace(face: Face): Boolean {
        val b = face.boundingBox
        val width = b.width().toFloat()
        val height = b.height().toFloat()
        if (height <= 0f || width <= 0f) return false

        val aspectRatio = width / height
        if (aspectRatio !in 0.5f..1.5f) return false

        // Require at least both eyes and nose — covered faces lack these landmarks
        val hasLeftEye = face.getLandmark(FaceLandmark.LEFT_EYE) != null
        val hasRightEye = face.getLandmark(FaceLandmark.RIGHT_EYE) != null
        val hasNose = face.getLandmark(FaceLandmark.NOSE_BASE) != null
        return hasLeftEye && hasRightEye && hasNose
    }
```

**Step 4: Build the Android app**

Run: `cd android && ./gradlew assembleDebug`

Expected: BUILD SUCCESSFUL

**Step 5: Commit**

```bash
git add android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt
git commit -m "fix: enable ML Kit landmarks and filter faces missing eyes/nose"
```

---

## Task 5: Android — Add staleness timeout to HybridFaceOverlay

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/components/HybridFaceOverlay.kt:320-330` (AnimatedFaceState)
- Modify: `android/app/src/main/java/com/iams/app/ui/components/HybridFaceOverlay.kt:64-110` (LaunchedEffect block)

**Step 1: Add lastUpdatedAt to AnimatedFaceState**

Replace lines 320-330:

```kotlin
private class AnimatedFaceState(
    val x1: Animatable<Float, *>,
    val y1: Animatable<Float, *>,
    val x2: Animatable<Float, *>,
    val y2: Animatable<Float, *>,
    val alpha: Animatable<Float, *>,
    var name: String?,
    var confidence: Float,
    var status: String,
    var unknownSince: Long = 0L,
    var lastUpdatedAt: Long = System.currentTimeMillis(),
)
```

**Step 2: Add staleness constant at the top of the file**

After line 27 (`private const val BACKEND_KEY_OFFSET = 100_000`), add:

```kotlin
/** Maximum age (ms) before a track is considered stale and faded out. */
private const val STALE_TRACK_TIMEOUT_MS = 500L
```

**Step 3: Add the kotlinx.coroutines.delay import**

At the top of the file (with the other imports), ensure this import exists:

```kotlin
import kotlinx.coroutines.delay
```

**Step 4: Update the LaunchedEffect to set lastUpdatedAt**

In the existing `LaunchedEffect(resolvedTracks)` block (lines 65-110), after each position update for existing faces (around line 83 where `existing.name = rt.name`), add:

```kotlin
                existing.lastUpdatedAt = System.currentTimeMillis()
```

And for newly created states (around line 106 where the state is added to animatedFaces), the default value in the constructor already sets it to `System.currentTimeMillis()`.

**Step 5: Add staleness sweep LaunchedEffect**

After the existing `LaunchedEffect(resolvedTracks)` block (after line 110, before the `Canvas` block), add a new LaunchedEffect:

```kotlin
    // Staleness sweep: fade out and remove tracks not refreshed within timeout
    LaunchedEffect(Unit) {
        while (true) {
            delay(200L)
            val now = System.currentTimeMillis()
            val stale = animatedFaces.entries.filter { (_, state) ->
                (now - state.lastUpdatedAt) > STALE_TRACK_TIMEOUT_MS
            }
            for ((key, state) in stale) {
                // Fade out, then remove
                launch { state.alpha.animateTo(0f, tween(150)) }
                delay(160L)
                animatedFaces.remove(key)
            }
        }
    }
```

**Step 6: Build the Android app**

Run: `cd android && ./gradlew assembleDebug`

Expected: BUILD SUCCESSFUL

**Step 7: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/components/HybridFaceOverlay.kt
git commit -m "fix: add 500ms staleness timeout to overlay as ghost box safety net"
```

---

## Task 6: Integration Test — Full stack verification

**Step 1: Rebuild backend with all changes**

Run: `docker compose up -d --build api-gateway`

**Step 2: Run all backend tests**

Run: `docker compose exec api-gateway python -m pytest tests/ -q`

Expected: All tests pass.

**Step 3: Build Android app with all changes**

Run: `cd android && ./gradlew assembleDebug`

Expected: BUILD SUCCESSFUL

**Step 4: Manual verification checklist**

With a live camera feed:
- [ ] Face visible → bounding box appears within ~200ms
- [ ] Face walks out of frame → box disappears within ~500ms
- [ ] Face covered by another person → box disappears within ~500ms
- [ ] Face covered by hands → box disappears within ~500ms
- [ ] Brief occlusion (<0.5s, e.g., someone walks past) → box may briefly disappear and reappear (acceptable)
- [ ] No floating/orphaned boxes when no faces are visible
- [ ] Multiple faces: covering one doesn't affect the other's box

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: ghost bounding box elimination — multi-layer defense"
```

---

## Summary of All Changes

| # | File | Change | Layer |
|---|------|--------|-------|
| 1 | `backend/app/config.py:91` | `TRACK_LOST_TIMEOUT` 2.0 → 0.5 | Backend |
| 2 | `backend/app/services/realtime_tracker.py:98` | `track_activation_threshold` 0.1 → 0.25 | Backend |
| 3 | `backend/app/services/realtime_tracker.py:140-158` | Min face size filter (1% frame area) | Backend |
| 4 | `android/.../MlKitFrameSink.kt:66-75` | `LANDMARK_MODE_ALL`, `minFaceSize` 0.15 | ML Kit |
| 5 | `android/.../MlKitFrameSink.kt:207-215` | Require eyes + nose landmarks | ML Kit |
| 6 | `android/.../HybridFaceOverlay.kt` | 500ms staleness timeout + fade-out | Overlay |

## Lessons

- ByteTrack's `track_activation_threshold=0.1` was far too permissive for face tracking — it allowed nearly any blob to become a tracked face. 0.25 is still generous but eliminates the worst false positives.
- ML Kit with `LANDMARK_MODE_NONE` cannot distinguish a visible face from a face-shaped blob. Always enable landmarks when face visibility matters for display.
- `TRACK_LOST_TIMEOUT=2.0s` was designed for general object tracking where re-identification is expensive. For face tracking with live display, 0.5s is sufficient — brief occlusions are sub-second.
- Display-layer staleness timeouts are essential safety nets even when upstream pipelines are correct. Network jitter and frame drops happen.
