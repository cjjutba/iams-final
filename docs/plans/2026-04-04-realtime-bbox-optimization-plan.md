# Real-Time Bounding Box Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix false positives, ghost tracks, delayed bounding boxes, and improve tracking smoothness in the live feed.

**Architecture:** Five surgical fixes across backend (Python) and Android (Kotlin). No architectural changes — just bug fixes and parameter tuning.

**Tech Stack:** Python (FastAPI, FAISS, ByteTrack), Kotlin (Jetpack Compose, ML Kit)

---

### Task 1: Fix FAISS user_map Sync (False Positive Bug)

**Files:**
- Modify: `backend/app/main.py:103` (startup)
- Modify: `backend/app/main.py:311` (self-heal)
- Modify: `backend/app/routers/presence.py:126` (manual start)

Every call to `faiss_manager.load_or_create_index()` must be immediately followed by `faiss_manager.rebuild_user_map_from_db()`. Currently three call sites skip this.

**Step 1: Fix startup in main.py**

In `backend/app/main.py` around line 103, after `faiss_manager.load_or_create_index()`, add:
```python
faiss_manager.rebuild_user_map_from_db()
```

**Step 2: Fix self-heal in main.py lifecycle**

In `backend/app/main.py` around line 311, the self-heal block does:
```python
if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
    faiss_manager.load_or_create_index()
if not faiss_manager.user_map:
    ...reconcile...
```

Change to always rebuild user_map after loading:
```python
if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()
if not faiss_manager.user_map:
    faiss_manager.rebuild_user_map_from_db()
```

**Step 3: Fix manual session start in presence.py**

In `backend/app/routers/presence.py` around line 126, same pattern:
```python
if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()
if not faiss_manager.user_map:
    faiss_manager.rebuild_user_map_from_db()
```

**Step 4: Verify** — check the Redis pubsub listener at `faiss_manager.py:513` already calls both (it does — confirmed).

**Step 5: Commit**
```
fix(backend): always rebuild FAISS user_map after index reload

Three call sites loaded the FAISS index without rebuilding user_map,
causing recognized faces to appear as "Unknown" when the map was stale.
```

---

### Task 2: Add Unknown Track Deduplication (Ghost Tracks Bug)

**Files:**
- Modify: `backend/app/services/realtime_tracker.py:221-233`

Currently only recognized tracks (with `user_id`) are deduplicated. Unknown tracks with overlapping bounding boxes can pile up, causing "3 Unknown" in the list but only 2 visible boxes.

**Step 1: Add IoU-based deduplication for unknown tracks after the existing user_id dedup**

After line 233 (`results = deduped_results`), add:
```python
# 6b. Deduplicate unknown tracks by bbox IoU — keep highest confidence
unknown_tracks = [r for r in results if r.user_id is None]
known_tracks = [r for r in results if r.user_id is not None]
deduped_unknown: list[TrackResult] = []
for track in unknown_tracks:
    is_dup = False
    for j, existing in enumerate(deduped_unknown):
        iou = self._compute_iou_norm(track.bbox, existing.bbox)
        if iou > 0.3:
            # Overlapping unknown — keep higher confidence
            if track.confidence > existing.confidence:
                deduped_unknown[j] = track
            is_dup = True
            break
    if not is_dup:
        deduped_unknown.append(track)
results = known_tracks + deduped_unknown
```

**Step 2: Add the normalized bbox IoU helper**

Add this method to the `RealtimeTracker` class (after `_compute_iou`):
```python
@staticmethod
def _compute_iou_norm(box_a: list[float], box_b: list[float]) -> float:
    """Compute IoU between two normalized [x1, y1, x2, y2] bboxes."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0
```

**Step 3: Commit**
```
fix(backend): deduplicate overlapping unknown tracks by bbox IoU

Unknown tracks were never deduplicated, causing ghost entries in the
detected list (e.g., "3 Unknown" but only 2 visible boxes).
```

---

### Task 3: Remove Unknown Label Delay (Instant Bounding Boxes)

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/components/HybridFaceOverlay.kt:24,148-150`

The 2-second `UNKNOWN_LABEL_DELAY_MS` hides newly-detected unknown faces. Remove this delay so boxes appear instantly.

**Step 1: Change the delay constant to 0**

Line 24:
```kotlin
// Before:
private const val UNKNOWN_LABEL_DELAY_MS = 2000L
// After:
private const val UNKNOWN_LABEL_DELAY_MS = 0L
```

**Step 2: Simplify the rendering check**

Lines 148-150 currently skip unknown faces during the delay. With delay=0 this block is effectively dead code, but simplify it for clarity:
```kotlin
// Before:
if (state.status == "unknown") {
    if (state.unknownSince <= 0L || (now - state.unknownSince) < UNKNOWN_LABEL_DELAY_MS) continue
}
// After:
// (remove the block entirely — unknown faces render immediately)
```

Also remove the now-unnecessary `unknownSince` tracking from the animation state updates (lines 85-89 and 104). Set `unknownSince = 0L` unconditionally.

**Step 3: Commit**
```
fix(android): remove 2s delay before showing Unknown bounding boxes

Faces now show "Unknown" label immediately upon detection instead
of waiting 2 seconds, making the UI feel more responsive.
```

---

### Task 4: Increase ML Kit Frame Rate (Smoother Tracking)

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt:64`

Change `processEveryN` from 3 to 2, giving ~15fps ML Kit detection from 30fps WebRTC input. The ML Kit processing takes ~15-25ms on 480x360 frames, well within the 66ms budget at 15fps.

**Step 1: Update the frame skip constant**

Line 64:
```kotlin
// Before:
private val processEveryN = 3
// After:
private val processEveryN = 2
```

Update the comment on line 62:
```kotlin
// Before:
// Process every Nth frame to reduce ML Kit load (3 = ~10fps detection at 30fps input).
// After:
// Process every Nth frame to reduce ML Kit load (2 = ~15fps detection at 30fps input).
```

**Step 2: Commit**
```
perf(android): increase ML Kit detection rate to 15fps for smoother tracking

Changed processEveryN from 3 to 2, giving ~15fps face detection from
30fps WebRTC input. ML Kit budget is ~25ms per frame on 480x360 downsampled
frames, well within the 66ms frame interval.
```

---

### Task 5: Align Detected Tab Count with Visible Boxes

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedScreen.kt:263,469,527-528`

The Detected tab counts ALL backend tracks including "pending" ones that never render. Filter to only count tracks with status "recognized" or "unknown".

**Step 1: Filter tracks for display**

At line 263, filter before counting:
```kotlin
// Before:
detectedCount = tracks.size
// After:
detectedCount = tracks.count { it.status == "recognized" || it.status == "unknown" }
```

At line 469:
```kotlin
// Before:
text = "${tracks.count { it.status == "recognized" }} recognized / ${tracks.size} detected",
// After:
val displayTracks = tracks.filter { it.status == "recognized" || it.status == "unknown" }
text = "${displayTracks.count { it.status == "recognized" }} recognized / ${displayTracks.size} detected",
```

At lines 527-528:
```kotlin
// Before:
val recognized = tracks.filter { it.status == "recognized" && it.name != null }
val unknown = tracks.filter { it.status != "recognized" }
// After:
val recognized = tracks.filter { it.status == "recognized" && it.name != null }
val unknown = tracks.filter { it.status == "unknown" }
```

**Step 2: Commit**
```
fix(android): align detected tab count with visible bounding boxes

Filter out "pending" tracks from display counts and lists so the
number shown matches the actual visible boxes on screen.
```

---

## Lessons

- Every `load_or_create_index()` call MUST be followed by `rebuild_user_map_from_db()` — forgetting this causes silent false negatives in recognition.
- Unknown tracks need spatial deduplication (by IoU) just like recognized tracks need user_id deduplication — ByteTrack can assign different IDs to overlapping detections.
- Hardcoded UX delays (2s) compound with real pipeline latency and should be zero for real-time systems.
- ML Kit at processEveryN=2 (15fps) is the sweet spot — 30fps wastes CPU with no visual improvement, 10fps causes visible jitter.
