# False Positive Face Detection Reduction — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate false positive face bounding boxes on non-face objects (posters, clocks, round objects, random patterns) on both the Android Live Feed and backend attendance pipeline.

**Architecture:** Add post-detection filtering in ML Kit (landmark validation, aspect ratio check, static face suppression) and raise SCRFD detection threshold on the backend. All changes are in existing files — no new files needed.

**Tech Stack:** Kotlin (ML Kit Face Detection API), Python (InsightFace/SCRFD config)

---

### Task 1: Enable ML Kit Landmark Detection and Raise Min Face Size

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt:48-57`

**Step 1: Update FaceDetectorOptions**

Change the `faceDetector` initialization from:
```kotlin
private val faceDetector = FaceDetection.getClient(
    FaceDetectorOptions.Builder()
        .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
        .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
        .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
        .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
        .setMinFaceSize(0.10f)
        .enableTracking()
        .build()
)
```

To:
```kotlin
private val faceDetector = FaceDetection.getClient(
    FaceDetectorOptions.Builder()
        .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
        .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
        .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
        .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
        .setMinFaceSize(0.13f)
        .enableTracking()
        .build()
)
```

Changes: `LANDMARK_MODE_NONE` → `LANDMARK_MODE_ALL`, `minFaceSize` 0.10 → 0.13.

**Step 2: Add required import**

Add at the top of the file:
```kotlin
import com.google.mlkit.vision.face.FaceLandmark
```

**Step 3: Build to verify compilation**

Run: `cd android && ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL

**Step 4: Commit**

```bash
git add android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt
git commit -m "feat(android): enable ML Kit landmark detection and raise minFaceSize to 0.13"
```

---

### Task 2: Add Landmark + Aspect Ratio Post-Detection Filter

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt:133-147`

**Step 1: Add filtering function**

Add this private function to `MlKitFrameSink` class, before the `close()` method (before line 159):

```kotlin
/**
 * Filters out false positive face detections by checking:
 * 1. Landmark presence — must have at least one eye AND nose
 * 2. Aspect ratio — width/height must be between 0.5 and 1.5
 */
private fun isValidFace(face: com.google.mlkit.vision.face.Face): Boolean {
    // Landmark check: must have at least one eye + nose
    val hasLeftEye = face.getLandmark(FaceLandmark.LEFT_EYE) != null
    val hasRightEye = face.getLandmark(FaceLandmark.RIGHT_EYE) != null
    val hasNose = face.getLandmark(FaceLandmark.NOSE_BASE) != null

    if (!hasNose || (!hasLeftEye && !hasRightEye)) {
        return false
    }

    // Aspect ratio check: valid faces are roughly 0.5–1.5 width/height
    val b = face.boundingBox
    val width = b.width().toFloat()
    val height = b.height().toFloat()
    if (height <= 0f) return false

    val aspectRatio = width / height
    if (aspectRatio < 0.5f || aspectRatio > 1.5f) {
        return false
    }

    return true
}
```

**Step 2: Apply filter in processFrame**

In the `processFrame` method, change the success listener from:

```kotlin
faceDetector.process(inputImage)
    .addOnSuccessListener { faces ->
        _faces.value = faces.map { face ->
            val b = face.boundingBox
```

To:

```kotlin
faceDetector.process(inputImage)
    .addOnSuccessListener { faces ->
        _faces.value = faces.filter { isValidFace(it) }.map { face ->
            val b = face.boundingBox
```

This is a single `.filter { isValidFace(it) }` inserted before `.map`.

**Step 3: Build to verify compilation**

Run: `cd android && ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL

**Step 4: Commit**

```bash
git add android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt
git commit -m "feat(android): add landmark and aspect ratio filtering to reduce false positives"
```

---

### Task 3: Add Static Face Suppression

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt`

**Step 1: Add static tracking data structures**

Add these properties to the `MlKitFrameSink` class, after the `nv21Buffer` declaration (after line 67):

```kotlin
// Static face suppression: tracks bbox center per face ID over time
private data class FacePositionRecord(val centerX: Float, val centerY: Float, val timeMs: Long)

/** Per-face position history for static suppression. Key = ML Kit tracking ID. */
private val positionHistory = mutableMapOf<Int, MutableList<FacePositionRecord>>()

companion object {
    private const val TAG = "MlKitFrameSink"
    private const val STATIC_THRESHOLD = 0.02f       // 2% of frame dimension
    private const val STATIC_DURATION_MS = 5_000L     // 5 seconds without movement = static
    private const val POSITION_HISTORY_MAX = 60        // max entries per face (~5s at ~12fps processing rate)
}
```

Note: The existing companion object (lines 41-43) must be replaced by the new one above that includes both `TAG` and the static suppression constants.

**Step 2: Add static detection method**

Add this method to the class, after the `isValidFace` method:

```kotlin
/**
 * Returns true if this face has been stationary for [STATIC_DURATION_MS].
 * A face is considered stationary if its center hasn't moved more than
 * [STATIC_THRESHOLD] (2% of frame) from its initial tracked position.
 */
private fun isStaticFace(faceId: Int?, centerX: Float, centerY: Float): Boolean {
    val id = faceId ?: return false  // can't track without ID
    val now = System.currentTimeMillis()
    val record = FacePositionRecord(centerX, centerY, now)

    val history = positionHistory.getOrPut(id) { mutableListOf() }
    history.add(record)

    // Trim old entries beyond our window
    history.removeAll { now - it.timeMs > STATIC_DURATION_MS + 1000L }

    // Keep bounded
    while (history.size > POSITION_HISTORY_MAX) {
        history.removeAt(0)
    }

    // Need at least 2 seconds of history before declaring static
    val oldest = history.firstOrNull() ?: return false
    if (now - oldest.timeMs < 2_000L) return false

    // Check if max displacement from first recorded position exceeds threshold
    val maxDisplacement = history.maxOf { record ->
        maxOf(
            kotlin.math.abs(record.centerX - oldest.centerX),
            kotlin.math.abs(record.centerY - oldest.centerY)
        )
    }

    return maxDisplacement < STATIC_THRESHOLD && (now - oldest.timeMs >= STATIC_DURATION_MS)
}
```

**Step 3: Integrate static suppression into processFrame**

In the `processFrame` method's success listener, update the filter+map chain. Change from:

```kotlin
_faces.value = faces.filter { isValidFace(it) }.map { face ->
    val b = face.boundingBox
    val mlFace = MlKitFace(
        x1 = (b.left / effW).coerceIn(0f, 1f),
        y1 = (b.top / effH).coerceIn(0f, 1f),
        x2 = (b.right / effW).coerceIn(0f, 1f),
        y2 = (b.bottom / effH).coerceIn(0f, 1f),
        faceId = face.trackingId
    )
    Log.d(TAG, "raw=${width}x${height} rot=$rotation eff=${effW.toInt()}x${effH.toInt()} face=[${b.left},${b.top},${b.right},${b.bottom}] norm=[${mlFace.x1},${mlFace.y1},${mlFace.x2},${mlFace.y2}]")
    mlFace
}
```

To:

```kotlin
val validFaces = faces.filter { isValidFace(it) }

_faces.value = validFaces.mapNotNull { face ->
    val b = face.boundingBox
    val x1 = (b.left / effW).coerceIn(0f, 1f)
    val y1 = (b.top / effH).coerceIn(0f, 1f)
    val x2 = (b.right / effW).coerceIn(0f, 1f)
    val y2 = (b.bottom / effH).coerceIn(0f, 1f)

    // Static face suppression: skip faces that haven't moved for 5+ seconds (posters/photos)
    val centerX = (x1 + x2) / 2f
    val centerY = (y1 + y2) / 2f
    if (isStaticFace(face.trackingId, centerX, centerY)) {
        Log.d(TAG, "Suppressed static face id=${face.trackingId}")
        return@mapNotNull null
    }

    val mlFace = MlKitFace(
        x1 = x1, y1 = y1, x2 = x2, y2 = y2,
        faceId = face.trackingId
    )
    Log.d(TAG, "raw=${width}x${height} rot=$rotation eff=${effW.toInt()}x${effH.toInt()} face=[${b.left},${b.top},${b.right},${b.bottom}] norm=[${mlFace.x1},${mlFace.y1},${mlFace.x2},${mlFace.y2}]")
    mlFace
}

// Clean up position history for faces no longer tracked
val activeFaceIds = validFaces.mapNotNull { it.trackingId }.toSet()
positionHistory.keys.removeAll { it !in activeFaceIds }
```

**Step 4: Build to verify compilation**

Run: `cd android && ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL

**Step 5: Commit**

```bash
git add android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt
git commit -m "feat(android): add static face suppression to filter posters and photos"
```

---

### Task 4: Raise Backend SCRFD Detection Threshold

**Files:**
- Modify: `backend/app/config.py:55`

**Step 1: Update threshold**

Change line 55 from:
```python
INSIGHTFACE_DET_THRESH: float = 0.3  # Lower threshold for surveillance cameras
```

To:
```python
INSIGHTFACE_DET_THRESH: float = 0.5  # Detection confidence minimum (aligned with attendance engine filter)
```

**Step 2: Run backend tests**

Run: `cd backend && pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(backend): raise SCRFD det_thresh from 0.3 to 0.5 to reduce false positives"
```

---

### Task 5: Manual Integration Testing

**Step 1: Start backend**

Run: `docker compose up -d`

**Step 2: Build and install Android app**

Run: `cd android && ./gradlew installDebug`

**Step 3: Test with faculty Live Feed**

Open the faculty Live Feed screen. Verify:
- [ ] Real student faces are detected with bounding boxes
- [ ] Round objects (clocks, speakers) no longer have bounding boxes
- [ ] Posters/photos on walls get suppressed after ~5 seconds
- [ ] Elongated/wide false detections are gone
- [ ] Backend attendance scan no longer produces "Unknown" for non-face objects
- [ ] 30fps feel is preserved (no visible lag from landmark mode)

**Step 4: Commit final verification note (if any tweaks needed)**

```bash
git commit -m "chore: integration testing complete for false positive reduction"
```

## Lessons

- ML Kit `PERFORMANCE_MODE_FAST` without landmark detection is too permissive for surveillance — always enable at least `LANDMARK_MODE_ALL` when accuracy matters.
- A low SCRFD det_thresh (0.3) that gets filtered at 0.5 downstream wastes compute and generates false WebSocket broadcasts.
- Static object suppression via position tracking is the only reliable way to filter posters/photos that have genuine facial features — landmark and aspect ratio filters alone won't catch them.
