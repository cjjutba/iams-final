# Live Feed Performance Fix — Design

**Date:** 2026-03-20
**Status:** Approved
**Branch:** feat/architecture-redesign

## Problem

The Live Feed screen in the Android app renders at ~0.5fps (1 frame per 2 seconds) while the Reolink native app shows smooth 20fps on the same camera and network. The root cause is not the stream source — it's 5 compounding implementation bottlenecks in the Android video pipeline.

## Root Cause Analysis

### 1. 20MB GPU Readback (Critical)

`textureView.bitmap` copies the full 2560x1920 frame from GPU → CPU memory (~20MB). This takes 15-30ms, during which ExoPlayer cannot update the TextureView. At 5fps detection rate, the video freezes for 75-150ms per second.

### 2. UI Thread Contention (Critical)

The face detection polling loop runs in a `LaunchedEffect` (Main dispatcher). Bitmap capture, ML Kit submission, and Compose Canvas overlay all compete with ExoPlayer for the same UI thread.

### 3. Aggressive Buffering (High)

`minBufferMs = 500` forces ExoPlayer to accumulate 500ms of video before rendering, creating a stop-start cycle instead of continuous playback.

### 4. Per-Frame Bitmap Allocation (High)

`textureView.bitmap` (no argument) allocates a new 20MB Bitmap every call. At 5fps = 100MB/sec of garbage, causing GC pauses that drop video frames.

### 5. Unnecessary Recomposition (Medium)

Every ML Kit result triggers a `StateFlow` update, which recomposes the `FaceOverlay` Canvas 5x/sec on the UI thread.

## Solution: Decouple Detection from Rendering

Keep the same architecture (ExoPlayer + ML Kit + Canvas overlay) but fix the implementation so the video path and detection path don't interfere.

### Change 1: ExoPlayer Buffer Tuning

**File:** `RtspVideoPlayer.kt`

| Setting | Before | After | Why |
|---------|--------|-------|-----|
| `minBufferMs` | 500 | 100 | Start rendering almost immediately |
| `maxBufferMs` | 3000 | 500 | Don't accumulate stale frames |
| `bufferForPlaybackAfterRebufferMs` | 500 | 100 | Recover from stalls faster |
| `setForceUseRtpTcp` | false (UDP) | true (TCP) | Reliable over WiFi, no packet loss |

### Change 2: Pre-allocated Bitmap + GPU Resize

**File:** `FaceDetectionProcessor.kt`

- Pre-allocate a single 640×480 Bitmap in the constructor (reused every frame)
- Use `textureView.getBitmap(preallocatedBitmap)` — GPU does the resize in hardware
- Readback drops from 20MB → 1.2MB (15× reduction)
- Remove manual `Bitmap.createScaledBitmap` (no longer needed)
- No `bitmap.recycle()` on the reusable bitmap — only recycle in `close()`

### Change 3: Background Thread for Face Detection

**File:** `FacultyLiveFeedScreen.kt`

- Move the polling loop to `Dispatchers.Default` (background thread)
- Use `withContext(Dispatchers.Main)` only for `textureView.getBitmap()` (requires UI thread)
- Reduce detection rate from 5fps (200ms) → 3fps (333ms)

### Change 4: Reduce Overlay Recomposition

**File:** `FaceOverlay.kt`

- Use `snapshotFlow` or `derivedStateOf` to skip redundant recompositions when detection results haven't meaningfully changed

## Expected Outcome

- Video: 15-20fps smooth playback (matching Reolink quality)
- Detection: 2-3fps yellow bounding boxes (responsive, not blocking video)
- Memory: ~1.2MB per detection frame instead of 20MB (no GC pressure)

## Escalation Path

If Approach A doesn't achieve 15+fps, escalate to Approach B: replace TextureView with SurfaceView (hardware compositor path) + ImageReader for frame sampling.
