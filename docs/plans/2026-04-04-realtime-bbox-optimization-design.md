# Real-Time Bounding Box Optimization Design

**Date:** 2026-04-04
**Status:** Approved

## Problem

Five issues with the live feed bounding box rendering:

1. **False positive**: Registered face shows "Unknown" due to stale FAISS `user_map` after index reload
2. **Ghost tracks**: Detected tab shows more Unknown entries than visible boxes on screen
3. **Missing boxes**: No bounding boxes drawn when WebSocket hasn't delivered backend tracks yet
4. **Delayed display**: 2-second hardcoded delay before "Unknown" label appears
5. **Tracking jitter**: ML Kit processes every 3rd frame (~10fps), causing less smooth tracking

## Approach: Backend-First Fix (Approach A)

Surgical fixes targeting root causes. No architecture changes.

### Fix 1: FAISS user_map Sync (False Positive)

**File:** `backend/app/services/ml/faiss_manager.py`

Ensure `rebuild_user_map_from_db()` is always called after `load_or_create_index()`. The Redis pubsub listener and any code path that reloads the index must rebuild the user_map immediately after.

### Fix 2: Unknown Track Deduplication (Ghost Tracks)

**File:** `backend/app/services/realtime_tracker.py`

Unknown tracks with overlapping bounding boxes (IoU > 0.5) should be deduplicated — keep only the highest-confidence detection. Currently only recognized tracks (with user_id) are deduplicated.

### Fix 3: Remove Unknown Label Delay (Delayed Display)

**File:** `android/.../HybridFaceOverlay.kt`

Remove or reduce the 2-second `UNKNOWN_LABEL_DELAY_MS`. Faces should show "Unknown" immediately upon detection.

### Fix 4: Increase ML Kit Frame Rate (Smoother Tracking)

**File:** `android/.../MlKitFrameSink.kt`

Change `processEveryN` from 3 to 2, giving ~15fps ML Kit detection from 30fps input. Still within the ~25ms per-frame ML Kit budget on the 480x360 downsampled frames.

### Fix 5: Align Detected Tab Count with Visible Boxes

**File:** `android/.../FacultyLiveFeedScreen.kt`

Filter out tracks that cannot render (no bbox, pending status) from the Detected tab count and list, so the count matches what's visible on screen.

## Lessons

- FAISS index reload without user_map rebuild silently breaks recognition — always pair them.
- Unknown tracks need spatial deduplication just like recognized tracks need user_id deduplication.
- Hardcoded UX delays (2s unknown label) compound with real pipeline latency, making the system feel sluggish.
