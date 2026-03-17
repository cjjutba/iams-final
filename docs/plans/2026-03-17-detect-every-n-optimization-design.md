# Detect-Every-N Pipeline Optimization Design

**Date:** 2026-03-17
**Branch:** feat/architecture-redesign
**Goal:** Smooth 15-20fps annotated output at 720p using detect-every-N, track-every-1 pattern

## Problem

Current pipeline runs SCRFD face detection on every frame at 640x480@10fps. Detection costs ~30-50ms per frame, which is the bottleneck preventing higher FPS and resolution.

## Approach: ByteTrack Kalman Prediction (Approach A)

Leverage ByteTrack's built-in Kalman filter. On non-detection frames, pass `Detections.empty()` to the tracker — it predicts positions from internal state. Bounding boxes glide smoothly between real detections.

## Design

### Resolution & Frame Pipeline

- RTSPReader reads at **1280x720** (720p) — compositing resolution
- Detection runs on **640x360 downscaled copy** (4x fewer pixels)
- Bounding boxes scaled back to 720p with `scale_factor = 2.0`
- FFmpegPublisher outputs 1280x720@15fps

### Run Loop

```
frame_count = 0
while running:
    frame = reader.read()

    if frame_count % N == 0:          # Detection frame (every 5th)
        small = cv2.resize(frame, (640, 360))
        raw_dets = detect_faces(small, scale=2.0)
        tracked = tracker.update_with_detections(detections)
        run recognition on new tracks (throttled)
    else:                              # Tracking-only frame
        tracked = tracker.update_with_detections(Detections.empty())

    annotate on full 720p frame
    publish
    frame_count += 1
```

- Detection frames: ~40-50ms (detect + track + annotate + publish)
- Tracking-only frames: ~2-3ms (predict + annotate + publish)
- Average per frame well under 66.7ms budget (15fps)

### Config

| Setting | Old | New |
|---|---|---|
| `PIPELINE_WIDTH` | 640 | 1280 |
| `PIPELINE_HEIGHT` | 480 | 720 |
| `PIPELINE_FPS` | 10 | 15 |
| `PIPELINE_DET_INTERVAL` | (new) | 5 |

### Publisher (720p bitrate)

- `b:v` → 2500k (was 1200k)
- `maxrate` → 3000k (was 1500k)
- `bufsize` → 1000k (was 500k)
- `g` → 15 (keyframe per second, matching FPS)

### Annotator (720p scaling)

- `corner_length` → 20 (was 15)
- `font_scale` → 0.55 (was 0.45)
- `bar_height` → 36 (was 30)

### Bbox Coordinate Scaling

`_detect_faces()` accepts `scale` parameter. After SCRFD returns bboxes on the small frame, multiply coordinates by scale before returning `sv.Detections`. ByteTrack stores 720p-space coordinates; everything downstream works unchanged.

Recognition crops from full 720p frame using already-scaled bboxes — no changes needed.

## Files Changed

| File | Change |
|---|---|
| `config.py` | Add `PIPELINE_DET_INTERVAL`, update width/height/fps |
| `video_pipeline.py` | Frame counter, detect-every-N, downscale, scale bboxes |
| `ffmpeg_publisher.py` | Bump bitrate/maxrate/bufsize/keyframe for 720p |
| `frame_annotator.py` | Scale corner_length, font_scale, bar_height |

No new files. No new dependencies. ~80 lines across 4 files.
