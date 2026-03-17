# Detect-Every-N Pipeline Optimization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Achieve smooth 15-20fps annotated output at 720p by running SCRFD detection every 5th frame and letting ByteTrack's Kalman filter predict positions on intermediate frames.

**Architecture:** RTSPReader reads 1280x720@15fps. Every 5th frame, downscale to 640x360, run SCRFD, scale bboxes back to 720p, feed to ByteTrack. On the other 4 frames, pass empty detections so ByteTrack predicts. Annotate and publish every frame at 720p.

**Tech Stack:** OpenCV (resize), supervision ByteTrack (Kalman prediction), FFmpeg (H.264 encoding at 720p), InsightFace SCRFD (face detection)

---

### Task 1: Add PIPELINE_DET_INTERVAL config setting

**Files:**
- Modify: `backend/app/config.py:94-99`

**Step 1: Add the setting**

In `config.py`, add `PIPELINE_DET_INTERVAL` after the existing pipeline settings and update defaults:

```python
# Video Pipeline
PIPELINE_ENABLED: bool = True
PIPELINE_FPS: int = 15
PIPELINE_WIDTH: int = 1280
PIPELINE_HEIGHT: int = 720
PIPELINE_DET_MODEL: str = "buffalo_sc"
PIPELINE_DET_INTERVAL: int = 5  # Run detection every Nth frame
```

**Step 2: Verify**

Run: `cd backend && python -c "from app.config import settings; print(settings.PIPELINE_FPS, settings.PIPELINE_WIDTH, settings.PIPELINE_HEIGHT, settings.PIPELINE_DET_INTERVAL)"`
Expected: `15 1280 720 5`

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add PIPELINE_DET_INTERVAL config, update defaults to 720p@15fps"
```

---

### Task 2: Add bbox scale parameter to _detect_faces

**Files:**
- Modify: `backend/app/pipeline/video_pipeline.py:228-247` (_detect_faces method)
- Test: `backend/tests/test_pipeline/test_video_pipeline.py`

**Step 1: Write the failing test**

Add to `test_video_pipeline.py`:

```python
def test_detect_faces_scales_bboxes(self):
    """Bboxes should be multiplied by scale factor."""
    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    config = self._make_config()
    pipeline = VideoAnalyticsPipeline(config)

    mock_face = MagicMock()
    mock_face.x = 50
    mock_face.y = 25
    mock_face.width = 40
    mock_face.height = 50
    mock_face.confidence = 0.90

    mock_detector = MagicMock()
    mock_detector.get_faces.return_value = [mock_face]
    pipeline._detector = mock_detector

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    result = pipeline._detect_faces(frame, scale=2.0)
    assert len(result) == 1
    # xyxy = [50, 25, 90, 75] * 2.0 = [100, 50, 180, 150]
    np.testing.assert_array_almost_equal(
        result.xyxy[0], [100, 50, 180, 150]
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py::TestVideoPipeline::test_detect_faces_scales_bboxes -v`
Expected: FAIL — `_detect_faces() got an unexpected keyword argument 'scale'`

**Step 3: Implement scale parameter**

Modify `_detect_faces` in `video_pipeline.py`:

```python
def _detect_faces(self, frame: np.ndarray, scale: float = 1.0) -> sv.Detections:
    """Run SCRFD face detection and return supervision Detections.

    Args:
        frame: BGR frame (possibly downscaled for detection).
        scale: Multiply bounding boxes by this factor to map back to
            the original (compositing) resolution.
    """
    if self._detector is None:
        return sv.Detections.empty()

    try:
        faces = self._detector.get_faces(frame)
        if not faces:
            return sv.Detections.empty()

        bboxes = np.array(
            [[f.x, f.y, f.x + f.width, f.y + f.height] for f in faces],
            dtype=np.float32,
        )
        if scale != 1.0:
            bboxes *= scale
        scores = np.array([f.confidence for f in faces], dtype=np.float32)
        return sv.Detections(xyxy=bboxes, confidence=scores)
    except Exception as e:
        logger.error(f"[Pipeline:{self.room_id}] Detection error: {e}")
        return sv.Detections.empty()
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py -v`
Expected: ALL PASS (including the new scale test and the existing no-scale test)

**Step 5: Commit**

```bash
git add backend/app/pipeline/video_pipeline.py backend/tests/test_pipeline/test_video_pipeline.py
git commit -m "feat: add scale parameter to _detect_faces for resolution mapping"
```

---

### Task 3: Implement detect-every-N run loop

**Files:**
- Modify: `backend/app/pipeline/video_pipeline.py:165-223` (_run_loop method)
- Test: `backend/tests/test_pipeline/test_video_pipeline.py`

**Step 1: Write the failing test**

Add to `test_video_pipeline.py`:

```python
def test_run_loop_detect_every_n(self):
    """Detection should only run every N frames, tracking runs every frame."""
    import supervision as sv
    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    config = self._make_config(width=1280, height=720, fps=15, det_interval=3)
    pipeline = VideoAnalyticsPipeline(config)

    # Mock all components
    frame_720p = np.zeros((720, 1280, 3), dtype=np.uint8)
    pipeline._reader = MagicMock()
    pipeline._reader.read.return_value = frame_720p
    pipeline._publisher = MagicMock()
    pipeline._publisher.write_frame.return_value = True
    pipeline._annotator = MagicMock()
    pipeline._annotator.annotate.return_value = frame_720p
    pipeline._tracker = MagicMock()
    pipeline._tracker.update_with_detections.return_value = sv.Detections.empty()
    pipeline._detector = MagicMock()
    pipeline._detector.get_faces.return_value = []

    # Run exactly 6 frames then stop
    call_count = 0
    original_running = True
    def stop_after_6(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count >= 6:
            pipeline._running = False
        return frame_720p

    pipeline._reader.read.side_effect = stop_after_6
    pipeline._running = True
    pipeline._run_loop()

    # With det_interval=3, detection runs on frames 0, 3 → 2 times in 6 frames
    assert pipeline._detector.get_faces.call_count == 2
    # Tracker is called every frame
    assert pipeline._tracker.update_with_detections.call_count == 6
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py::TestVideoPipeline::test_run_loop_detect_every_n -v`
Expected: FAIL — config key `det_interval` not used, detection runs every frame

**Step 3: Implement detect-every-N loop**

Replace `_run_loop` in `video_pipeline.py`:

```python
def _run_loop(self) -> None:
    """Main processing loop -- read, detect/track, recognize, annotate, publish.

    Detection runs every ``det_interval`` frames (configured via
    ``PIPELINE_DET_INTERVAL``).  On intermediate frames, ByteTrack predicts
    track positions using its internal Kalman filter.
    """
    cfg = self.config
    fps = cfg["fps"]
    frame_interval = 1.0 / fps
    det_interval = cfg.get("det_interval", settings.PIPELINE_DET_INTERVAL)
    comp_h, comp_w = cfg["height"], cfg["width"]
    det_w, det_h = comp_w // 2, comp_h // 2
    scale = comp_h / det_h

    last_state_push = 0.0
    last_recognition_check = 0.0
    frame_count = 0

    while self._running:
        loop_start = time.time()

        # Read latest frame (full resolution)
        frame = self._reader.read() if self._reader else None
        if frame is None:
            time.sleep(0.01)
            continue

        if frame_count % det_interval == 0:
            # --- Detection frame ---
            small = cv2.resize(frame, (det_w, det_h))
            detections = self._detect_faces(small, scale=scale)
            tracked = self._tracker.update_with_detections(detections)

            # Recognize new/unidentified tracks (throttled)
            now = time.time()
            if now - last_recognition_check > 0.2:
                self._recognize_new_tracks(frame, tracked)
                last_recognition_check = now
        else:
            # --- Tracking-only frame (Kalman prediction) ---
            tracked = self._tracker.update_with_detections(sv.Detections.empty())
            now = time.time()

        # Clean up stale identities
        self._cleanup_stale_tracks(tracked)

        # Build detection list for annotator
        det_list = self._build_detection_list(tracked)

        # Update HUD
        self._hud_info["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._hud_info["present_count"] = sum(
            1 for d in det_list if d["name"] is not None
        )

        # Annotate
        annotated = self._annotator.annotate(frame, det_list, self._hud_info)

        # Publish
        if self._publisher and not self._publisher.write_frame(annotated):
            logger.warning(f"[Pipeline:{self.room_id}] Publisher write failed, restarting")
            self._restart_publisher()

        # Publish state to Redis (throttled to 1 Hz)
        if self._redis and now - last_state_push > 1.0:
            self._publish_state_to_redis(det_list)
            last_state_push = now

        # Frame pacing
        elapsed = time.time() - loop_start
        sleep_time = frame_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        frame_count += 1
```

Note: The `time.sleep(0.1)` on no-frame is reduced to `0.01` for tighter frame pacing at 15fps.

**Step 4: Update `__init__` to read det_interval from config**

No change needed — `_run_loop` reads it via `cfg.get("det_interval", settings.PIPELINE_DET_INTERVAL)`.

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/pipeline/video_pipeline.py backend/tests/test_pipeline/test_video_pipeline.py
git commit -m "feat: implement detect-every-N track-every-1 pattern in run loop"
```

---

### Task 4: Update FFmpegPublisher for 720p bitrate

**Files:**
- Modify: `backend/app/pipeline/ffmpeg_publisher.py:59-69`

**Step 1: Update bitrate settings**

In `_build_ffmpeg_cmd`, replace the encoding params:

```python
cmd += [
    "-pix_fmt", "yuv420p",
    "-bf", "0",
    "-g", str(self.fps),
    "-b:v", "2500k",
    "-maxrate", "3000k",
    "-bufsize", "1000k",
    "-f", "rtsp",
    "-rtsp_transport", "tcp",
    self.rtsp_url,
]
```

Changes: `g` → `self.fps` (dynamic), `b:v` → 2500k, `maxrate` → 3000k, `bufsize` → 1000k.

**Step 2: Verify**

Run: `cd backend && python -c "
from app.pipeline.ffmpeg_publisher import FFmpegPublisher
p = FFmpegPublisher('rtsp://localhost/test', 1280, 720, 15)
cmd = p._build_ffmpeg_cmd()
print(' '.join(cmd))
assert '2500k' in cmd
assert '3000k' in cmd
print('OK')
"`
Expected: Command string with 2500k, 3000k, prints OK

**Step 3: Commit**

```bash
git add backend/app/pipeline/ffmpeg_publisher.py
git commit -m "feat: bump publisher bitrate for 720p output"
```

---

### Task 5: Scale FrameAnnotator for 720p

**Files:**
- Modify: `backend/app/pipeline/frame_annotator.py:36-43`

**Step 1: Update default sizes**

In `__init__`:

```python
def __init__(self, width: int, height: int) -> None:
    self.width = width
    self.height = height
    self.corner_length = 20
    self.box_thickness = 2
    self.font_scale = 0.55
    self.font_thickness = 1
    self.bar_height = 36
```

**Step 2: Verify visually (manual)**

This is a cosmetic change — verify when running the full pipeline.

**Step 3: Commit**

```bash
git add backend/app/pipeline/frame_annotator.py
git commit -m "feat: scale annotator dimensions for 720p"
```

---

### Task 6: Integration test — full detect-every-N loop

**Files:**
- Test: `backend/tests/test_pipeline/test_video_pipeline.py`

**Step 1: Write integration test**

```python
def test_tracking_only_frames_use_predicted_positions(self):
    """On non-detection frames, tracker should return predicted (non-empty)
    positions for existing tracks."""
    import supervision as sv
    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    config = self._make_config(width=1280, height=720, fps=15, det_interval=3)
    pipeline = VideoAnalyticsPipeline(config)

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Use a real ByteTrack instance
    pipeline._tracker = sv.ByteTrack(
        track_activation_threshold=0.20,
        lost_track_buffer=90,
        minimum_matching_threshold=0.7,
        frame_rate=15,
        minimum_consecutive_frames=1,
    )

    # Feed 3 detection frames to establish a track
    det = sv.Detections(
        xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
        confidence=np.array([0.9]),
    )
    for _ in range(3):
        pipeline._tracker.update_with_detections(det)

    # Now feed an empty detection (simulating tracking-only frame)
    tracked = pipeline._tracker.update_with_detections(sv.Detections.empty())

    # ByteTrack should predict the position (track not lost yet)
    assert len(tracked) >= 1, "Track should persist via Kalman prediction"
    assert tracked.tracker_id is not None
```

**Step 2: Run test**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py::TestVideoPipeline::test_tracking_only_frames_use_predicted_positions -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/test_pipeline/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/tests/test_pipeline/test_video_pipeline.py
git commit -m "test: add integration test for Kalman prediction on tracking-only frames"
```

---

### Task 7: Smoke test with live camera

**Step 1: Start the stack**

Run: `./scripts/dev-up.sh`

**Step 2: Start a pipeline via API or check logs**

Verify the pipeline starts at 1280x720@15fps in the logs. Check that:
- Detection runs every 5th frame (log frequency)
- Annotated stream plays smoothly via WebRTC on mobile
- Bounding boxes glide between detections (no stutter)

**Step 3: Final commit if any adjustments needed**
