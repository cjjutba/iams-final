# RTSP-Direct Server-Side Compositing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the fragmented WebSocket frame-push pipeline with a unified RTSP-direct video analytics pipeline that burns bounding boxes into the video stream server-side.

**Architecture:** Backend reads RTSP from mediamtx directly, runs SCRFD_500M + ByteTrack + ArcFace in a single pipeline process, composites annotations onto frames with OpenCV, re-encodes via FFmpeg, and publishes an annotated RTSP stream back to mediamtx. Mobile plays the annotated WebRTC stream with zero overlay code.

**Tech Stack:** OpenCV (RTSP read + drawing), supervision (ByteTrack), ONNX Runtime (SCRFD_500M + ArcFace), FFmpeg subprocess (H.264 encode + RTSP publish), Redis (pipeline ↔ FastAPI communication), mediamtx (RTSP ingest + WebRTC serving)

**Design Doc:** `docs/plans/2026-03-17-rtsp-direct-compositing-redesign.md`

---

## Phase 1: Backend Pipeline Building Blocks

### Task 1: Add new dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add supervision and update requirements**

Add under `# ===== ML / Face Recognition =====`:
```
supervision>=0.25.0
```

**Step 2: Install and verify**

Run: `cd backend && pip install supervision>=0.25.0`
Expected: Installs successfully, pulls numpy/scipy/opencv (already present)

**Step 3: Verify import**

Run: `cd backend && python -c "import supervision as sv; print(sv.__version__); t = sv.ByteTrack(); print('ByteTrack OK')"`
Expected: Version prints, "ByteTrack OK"

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add supervision library for ByteTrack tracking"
```

---

### Task 2: Create RTSPReader — threaded RTSP capture

**Files:**
- Create: `backend/app/pipeline/rtsp_reader.py`
- Create: `backend/app/pipeline/__init__.py`
- Test: `backend/tests/test_pipeline/test_rtsp_reader.py`

**Step 1: Create pipeline package**

Create `backend/app/pipeline/__init__.py` (empty file).

**Step 2: Write the failing test**

Create `backend/tests/test_pipeline/__init__.py` (empty) and `backend/tests/test_pipeline/test_rtsp_reader.py`:

```python
"""Tests for RTSPReader — threaded RTSP capture with latest-frame semantics."""

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestRTSPReader:
    """RTSPReader always returns the latest frame, dropping stale ones."""

    def test_read_returns_none_before_first_frame(self):
        from app.pipeline.rtsp_reader import RTSPReader

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.read.return_value = (False, None)
            mock_cap.isOpened.return_value = True
            mock_cap_cls.return_value = mock_cap

            reader = RTSPReader("rtsp://fake:8554/test")
            reader.start()
            time.sleep(0.1)
            assert reader.read() is None
            reader.stop()

    def test_read_returns_latest_frame(self):
        from app.pipeline.rtsp_reader import RTSPReader

        frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_b = np.ones((480, 640, 3), dtype=np.uint8) * 128

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            # Return frame_a first, then frame_b repeatedly
            mock_cap.read.side_effect = [
                (True, frame_a.copy()),
                (True, frame_b.copy()),
            ] + [(True, frame_b.copy())] * 100
            mock_cap_cls.return_value = mock_cap

            reader = RTSPReader("rtsp://fake:8554/test")
            reader.start()
            time.sleep(0.3)  # Let reader thread consume frames

            frame = reader.read()
            assert frame is not None
            assert frame.shape == (480, 640, 3)
            reader.stop()

    def test_stop_releases_capture(self):
        from app.pipeline.rtsp_reader import RTSPReader

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_cap_cls.return_value = mock_cap

            reader = RTSPReader("rtsp://fake:8554/test")
            reader.start()
            time.sleep(0.1)
            reader.stop()
            mock_cap.release.assert_called_once()

    def test_get_fps_returns_configured_value(self):
        from app.pipeline.rtsp_reader import RTSPReader

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_cap.get.return_value = 25.0
            mock_cap_cls.return_value = mock_cap

            reader = RTSPReader("rtsp://fake:8554/test", target_fps=15)
            assert reader.target_fps == 15
```

**Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_rtsp_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline'`

**Step 4: Write RTSPReader implementation**

Create `backend/app/pipeline/rtsp_reader.py`:

```python
"""Threaded RTSP reader with latest-frame semantics.

Continuously reads from an RTSP source in a background thread.
The main thread always gets the most recent frame — stale frames are dropped.
This prevents the OpenCV internal buffer from accumulating latency.
"""

import os
import threading
import time

import cv2
import numpy as np

from app.config import logger


class RTSPReader:
    """Thread-safe RTSP reader that always returns the latest frame."""

    def __init__(self, url: str, target_fps: int = 25):
        self.url = url
        self.target_fps = target_fps
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> "RTSPReader":
        """Open RTSP source and start background reader thread."""
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
            "|probesize;500000|analyzeduration;500000",
        )
        self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._stopped = False
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        return self

    def _reader_loop(self) -> None:
        """Continuously read frames, keeping only the latest."""
        while not self._stopped:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.1)
                continue
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.01)

    def read(self) -> np.ndarray | None:
        """Return the latest frame (or None if no frame available yet)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self) -> None:
        """Stop the reader thread and release the capture."""
        self._stopped = True
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
```

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_rtsp_reader.py -v`
Expected: All 4 tests PASS

**Step 6: Commit**

```bash
git add backend/app/pipeline/ backend/tests/test_pipeline/
git commit -m "feat: add RTSPReader with threaded latest-frame capture"
```

---

### Task 3: Create FrameAnnotator — server-side OSD drawing

**Files:**
- Create: `backend/app/pipeline/frame_annotator.py`
- Test: `backend/tests/test_pipeline/test_frame_annotator.py`

**Step 1: Write the failing test**

Create `backend/tests/test_pipeline/test_frame_annotator.py`:

```python
"""Tests for FrameAnnotator — server-side bounding box and HUD drawing."""

import numpy as np
import pytest


class TestFrameAnnotator:
    def test_annotate_empty_detections(self):
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hud = {"room_name": "Room 301", "timestamp": "2026-03-17 08:15",
               "subject": "CS101", "professor": "Prof. Santos",
               "present_count": 0, "total_count": 35}
        result = annotator.annotate(frame, [], hud)
        assert result.shape == (480, 640, 3)
        assert result.dtype == np.uint8
        # Top bar should have been drawn (non-zero pixels)
        assert result[10, 50].sum() > 0  # Text pixels are non-zero

    def test_annotate_with_detections(self):
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [
            {"bbox": (100, 100, 200, 200), "name": "Juan Dela Cruz",
             "student_id": "2021-0145", "confidence": 0.95,
             "track_state": "confirmed", "track_id": 1, "duration_sec": 135.0},
            {"bbox": (300, 100, 400, 200), "name": None,
             "student_id": None, "confidence": 0.0,
             "track_state": "new", "track_id": 2, "duration_sec": 5.0},
        ]
        hud = {"room_name": "Room 301", "timestamp": "2026-03-17 08:15",
               "subject": "CS101", "professor": "Prof. Santos",
               "present_count": 1, "total_count": 35}
        result = annotator.annotate(frame, detections, hud)
        assert result.shape == (480, 640, 3)
        # Green pixels near box 1 (confirmed = green)
        assert result[100, 100, 1] > 0 or result[100, 115, 1] > 0

    def test_corner_bracket_draws_lines_not_full_rect(self):
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [
            {"bbox": (100, 100, 300, 300), "name": "Test",
             "student_id": "0001", "confidence": 0.9,
             "track_state": "confirmed", "track_id": 1, "duration_sec": 10.0},
        ]
        hud = {"room_name": "R", "timestamp": "T", "subject": "S",
               "professor": "P", "present_count": 0, "total_count": 0}
        result = annotator.annotate(frame, detections, hud)
        # Middle of top edge should be black (corner brackets, not full rect)
        mid_x = (100 + 300) // 2
        assert result[100, mid_x].sum() == 0

    def test_color_coding_by_state(self):
        from app.pipeline.frame_annotator import COLORS

        assert "confirmed" in COLORS
        assert "unknown" in COLORS
        assert "new" in COLORS
        assert "lost" in COLORS
        assert "alert" in COLORS
        # Green for confirmed (BGR: B=0, G>0, R=0)
        assert COLORS["confirmed"][1] > 100
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_frame_annotator.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write FrameAnnotator implementation**

Create `backend/app/pipeline/frame_annotator.py`:

```python
"""Server-side frame annotator — draws bounding boxes, labels, and HUD bars.

Uses OpenCV drawing functions for enterprise-style corner bracket boxes,
color-coded by track state, with semi-transparent HUD bars.

Performance: ~3-5ms for 50 faces at 640x480.
"""

import cv2
import numpy as np

# Color palette (BGR)
COLORS = {
    "confirmed": (0, 200, 0),      # Green — recognized student
    "unknown":   (0, 200, 255),     # Yellow/amber — detected, not matched
    "new":       (255, 200, 0),     # Cyan — just appeared
    "lost":      (128, 128, 128),   # Gray — temporarily lost
    "alert":     (0, 0, 255),       # Red — early leave
}

_FONT = cv2.FONT_HERSHEY_SIMPLEX


class FrameAnnotator:
    """High-performance frame annotator with corner bracket boxes and HUD."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.corner_length = 15
        self.box_thickness = 2
        self.font_scale = 0.45
        self.font_thickness = 1
        self.bar_height = 30

    def annotate(
        self,
        frame: np.ndarray,
        detections: list[dict],
        hud_info: dict,
    ) -> np.ndarray:
        """Draw all annotations onto frame in-place and return it."""
        for det in detections:
            self._draw_detection(frame, det)
        self._draw_hud(frame, hud_info)
        return frame

    def _draw_detection(self, frame: np.ndarray, det: dict) -> None:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        state = det.get("track_state", "unknown")
        color = COLORS.get(state, COLORS["unknown"])

        # Corner brackets
        cl = min(self.corner_length, (x2 - x1) // 3, (y2 - y1) // 3)
        t = self.box_thickness
        # Top-left
        cv2.line(frame, (x1, y1), (x1 + cl, y1), color, t)
        cv2.line(frame, (x1, y1), (x1, y1 + cl), color, t)
        # Top-right
        cv2.line(frame, (x2, y1), (x2 - cl, y1), color, t)
        cv2.line(frame, (x2, y1), (x2, y1 + cl), color, t)
        # Bottom-left
        cv2.line(frame, (x1, y2), (x1 + cl, y2), color, t)
        cv2.line(frame, (x1, y2), (x1, y2 - cl), color, t)
        # Bottom-right
        cv2.line(frame, (x2, y2), (x2 - cl, y2), color, t)
        cv2.line(frame, (x2, y2), (x2, y2 - cl), color, t)

        # Label
        if det.get("name"):
            line1 = f"{det['name']}"
            if det.get("student_id"):
                line1 += f" ({det['student_id']})"
        else:
            line1 = "Unknown Face"

        conf = det.get("confidence", 0)
        tid = det.get("track_id", 0)
        dur = det.get("duration_sec", 0)
        mins, secs = int(dur // 60), int(dur % 60)
        line2 = f"{conf:.0%} | T#{tid} | {mins}m{secs:02d}s"

        (tw1, th1), bl1 = cv2.getTextSize(line1, _FONT, self.font_scale, self.font_thickness)
        (tw2, th2), _ = cv2.getTextSize(line2, _FONT, self.font_scale * 0.85, self.font_thickness)

        tw = max(tw1, tw2)
        pad = 3
        label_h = th1 + th2 + pad * 3

        # Position above box, or inside if near top
        if y1 > label_h + 5:
            lx, ly = x1, y1 - label_h - 2
        else:
            lx, ly = x1, y1 + 2

        # Label background (ROI-only blend for performance)
        bg_y1 = max(ly, 0)
        bg_y2 = min(ly + label_h, frame.shape[0])
        bg_x1 = max(lx, 0)
        bg_x2 = min(lx + tw + pad * 2, frame.shape[1])

        if bg_y2 > bg_y1 and bg_x2 > bg_x1:
            roi = frame[bg_y1:bg_y2, bg_x1:bg_x2]
            bg_color = np.array(color, dtype=np.uint16)
            blended = (roi.astype(np.uint16) * 102 // 255 + bg_color * 153 // 255).astype(np.uint8)
            frame[bg_y1:bg_y2, bg_x1:bg_x2] = blended

        # Text
        text_y = ly + pad + th1
        if 0 <= text_y < frame.shape[0] and 0 <= lx + pad < frame.shape[1]:
            cv2.putText(frame, line1, (lx + pad, text_y),
                        _FONT, self.font_scale, (255, 255, 255),
                        self.font_thickness, cv2.LINE_AA)
            cv2.putText(frame, line2, (lx + pad, text_y + th2 + pad),
                        _FONT, self.font_scale * 0.85, (200, 200, 200),
                        self.font_thickness, cv2.LINE_AA)

    def _draw_hud(self, frame: np.ndarray, info: dict) -> None:
        h, w = frame.shape[:2]
        bh = self.bar_height

        # Top bar
        roi_top = frame[0:bh, :]
        roi_top[:] = (roi_top.astype(np.uint16) * 102 // 255).astype(np.uint8)

        top_left = f"IAMS | {info.get('room_name', '')}"
        top_right = info.get("timestamp", "")
        cv2.putText(frame, top_left, (8, bh - 8),
                    _FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        (trw, _), _ = cv2.getTextSize(top_right, _FONT, 0.45, 1)
        cv2.putText(frame, top_right, (w - trw - 8, bh - 8),
                    _FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # Bottom bar
        roi_bot = frame[h - bh:h, :]
        roi_bot[:] = (roi_bot.astype(np.uint16) * 102 // 255).astype(np.uint8)

        present = info.get("present_count", 0)
        total = info.get("total_count", 0)
        bot_text = (
            f"{info.get('subject', '')} | {info.get('professor', '')} | "
            f"{present}/{total} Present"
        )
        cv2.putText(frame, bot_text, (8, h - 8),
                    _FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_frame_annotator.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/pipeline/frame_annotator.py backend/tests/test_pipeline/test_frame_annotator.py
git commit -m "feat: add FrameAnnotator with corner bracket boxes and HUD"
```

---

### Task 4: Create FFmpegPublisher — encode and push RTSP

**Files:**
- Create: `backend/app/pipeline/ffmpeg_publisher.py`
- Test: `backend/tests/test_pipeline/test_ffmpeg_publisher.py`

**Step 1: Write the failing test**

Create `backend/tests/test_pipeline/test_ffmpeg_publisher.py`:

```python
"""Tests for FFmpegPublisher — encodes frames and pushes RTSP."""

import platform
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestFFmpegPublisher:
    def test_build_command_linux(self):
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        with patch("platform.system", return_value="Linux"):
            pub = FFmpegPublisher(
                rtsp_url="rtsp://mediamtx:8554/room1/annotated",
                width=640, height=480, fps=25,
            )
            cmd = pub._build_ffmpeg_cmd()
            assert "libx264" in cmd
            assert "ultrafast" in cmd
            assert "zerolatency" in cmd
            assert "rtsp://mediamtx:8554/room1/annotated" in cmd
            assert "bgr24" in cmd

    def test_build_command_darwin(self):
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        with patch("platform.system", return_value="Darwin"):
            pub = FFmpegPublisher(
                rtsp_url="rtsp://mediamtx:8554/room1/annotated",
                width=640, height=480, fps=25,
            )
            cmd = pub._build_ffmpeg_cmd()
            # On Mac, should use VideoToolbox
            assert "h264_videotoolbox" in cmd or "libx264" in cmd

    def test_write_frame_sends_bytes_to_stdin(self):
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        pub = FFmpegPublisher("rtsp://fake:8554/test", 640, 480, 25)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pub._process = mock_proc

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pub.write_frame(frame)
        mock_proc.stdin.write.assert_called_once()
        written_bytes = mock_proc.stdin.write.call_args[0][0]
        assert len(written_bytes) == 640 * 480 * 3

    def test_no_bframes_in_command(self):
        """B-frames must be disabled for WebRTC compatibility."""
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        with patch("platform.system", return_value="Linux"):
            pub = FFmpegPublisher("rtsp://fake:8554/test", 640, 480, 25)
            cmd = pub._build_ffmpeg_cmd()
            # -bf 0 must be present
            bf_idx = cmd.index("-bf")
            assert cmd[bf_idx + 1] == "0"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_ffmpeg_publisher.py -v`
Expected: FAIL

**Step 3: Write FFmpegPublisher implementation**

Create `backend/app/pipeline/ffmpeg_publisher.py`:

```python
"""FFmpeg subprocess publisher — encodes raw frames to H.264 and pushes to RTSP.

Accepts raw BGR24 numpy arrays via write_frame(), pipes them to an FFmpeg
subprocess that encodes H.264 ultrafast/zerolatency and publishes to mediamtx.
"""

import platform
import subprocess

import numpy as np

from app.config import logger


class FFmpegPublisher:
    """Encode raw frames via FFmpeg and publish as RTSP stream."""

    def __init__(self, rtsp_url: str, width: int, height: int, fps: int):
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = fps
        self._process: subprocess.Popen | None = None

    def _build_ffmpeg_cmd(self) -> list[str]:
        """Build the FFmpeg command based on platform."""
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "pipe:0",
        ]

        if platform.system() == "Darwin":
            cmd += ["-c:v", "h264_videotoolbox", "-realtime", "1", "-allow_sw", "1"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"]

        cmd += [
            "-pix_fmt", "yuv420p",
            "-bf", "0",
            "-g", str(self.fps * 2),
            "-b:v", "800k",
            "-maxrate", "1000k",
            "-bufsize", "500k",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            self.rtsp_url,
        ]
        return cmd

    def start(self) -> None:
        """Launch FFmpeg subprocess."""
        cmd = self._build_ffmpeg_cmd()
        logger.info(f"Starting FFmpeg publisher → {self.rtsp_url}")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=self.width * self.height * 3 * 2,
        )

    def write_frame(self, frame: np.ndarray) -> bool:
        """Write a single BGR frame to FFmpeg. Returns False on pipe error."""
        if self._process is None or self._process.poll() is not None:
            return False
        try:
            self._process.stdin.write(frame.tobytes())
            return True
        except BrokenPipeError:
            logger.warning("FFmpeg publisher pipe broken")
            return False

    def stop(self) -> None:
        """Stop FFmpeg subprocess gracefully."""
        if self._process is not None:
            try:
                self._process.stdin.close()
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_ffmpeg_publisher.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/pipeline/ffmpeg_publisher.py backend/tests/test_pipeline/test_ffmpeg_publisher.py
git commit -m "feat: add FFmpegPublisher for H.264 encode + RTSP push"
```

---

### Task 5: Create VideoAnalyticsPipeline — the unified pipeline

**Files:**
- Create: `backend/app/pipeline/video_pipeline.py`
- Test: `backend/tests/test_pipeline/test_video_pipeline.py`

**Step 1: Write the failing test**

Create `backend/tests/test_pipeline/test_video_pipeline.py`:

```python
"""Tests for VideoAnalyticsPipeline — unified detect/track/recognize/annotate pipeline."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestVideoPipeline:
    def test_pipeline_creates_all_components(self):
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = {
            "room_id": "room-1",
            "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
            "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "Room 301",
            "det_model": "buffalo_sc",
        }
        pipeline = VideoAnalyticsPipeline(config)
        assert pipeline.room_id == "room-1"
        assert pipeline.config["width"] == 640

    def test_build_detection_list_from_tracked(self):
        """Verify detection list format matches FrameAnnotator expectations."""
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = {
            "room_id": "r1", "rtsp_source": "x", "rtsp_target": "x",
            "width": 640, "height": 480, "fps": 25,
            "room_name": "R", "det_model": "buffalo_sc",
        }
        pipeline = VideoAnalyticsPipeline(config)
        pipeline._identities = {
            1: {"user_id": "u1", "name": "Juan", "student_id": "2021-0001",
                "confidence": 0.95},
        }
        pipeline._track_start_times = {1: time.time() - 60, 2: time.time() - 5}

        # Simulate tracked detections
        import supervision as sv
        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200], [300, 100, 400, 200]], dtype=np.float32),
            confidence=np.array([0.9, 0.6]),
            tracker_id=np.array([1, 2]),
        )

        det_list = pipeline._build_detection_list(tracked)
        assert len(det_list) == 2
        assert det_list[0]["name"] == "Juan"
        assert det_list[0]["track_state"] == "confirmed"
        assert det_list[1]["name"] is None
        assert det_list[1]["track_state"] == "new"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py -v`
Expected: FAIL

**Step 3: Write VideoAnalyticsPipeline**

Create `backend/app/pipeline/video_pipeline.py`:

```python
"""Unified video analytics pipeline — RTSP in, annotated RTSP out.

Reads RTSP from mediamtx, runs face detection (SCRFD) + tracking (ByteTrack) +
recognition (ArcFace + FAISS), draws annotations, and publishes annotated stream.

Designed to run as a separate process per room.
"""

import json
import platform
import time
from datetime import datetime

import cv2
import numpy as np
import supervision as sv

from app.config import logger, settings
from app.pipeline.ffmpeg_publisher import FFmpegPublisher
from app.pipeline.frame_annotator import FrameAnnotator
from app.pipeline.rtsp_reader import RTSPReader


class VideoAnalyticsPipeline:
    """Single-room video analytics pipeline."""

    def __init__(self, config: dict):
        self.config = config
        self.room_id: str = config["room_id"]
        self._running = False

        # Sub-components (initialized on start)
        self._reader: RTSPReader | None = None
        self._publisher: FFmpegPublisher | None = None
        self._annotator: FrameAnnotator | None = None
        self._tracker: sv.ByteTrack | None = None
        self._detector = None  # InsightFace model (loaded on start)
        self._faiss = None     # FAISSManager (loaded on start)

        # State
        self._identities: dict[int, dict] = {}     # track_id -> identity info
        self._track_start_times: dict[int, float] = {}  # track_id -> first seen time
        self._confirmed_track_ids: set[int] = set()  # tracks with 3+ frames
        self._track_frame_counts: dict[int, int] = {}  # track_id -> frames seen
        self._hud_info: dict = {
            "room_name": config.get("room_name", ""),
            "timestamp": "",
            "subject": config.get("subject", ""),
            "professor": config.get("professor", ""),
            "present_count": 0,
            "total_count": config.get("total_enrolled", 0),
        }

        # Redis client (set externally before start)
        self._redis = None

    def _build_detection_list(self, tracked: sv.Detections) -> list[dict]:
        """Convert tracked detections to FrameAnnotator format."""
        now = time.time()
        result = []
        if tracked.tracker_id is None:
            return result

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i].tolist()

            # Track start time
            if tid not in self._track_start_times:
                self._track_start_times[tid] = now

            # Frame count for confirmation
            self._track_frame_counts[tid] = self._track_frame_counts.get(tid, 0) + 1
            if self._track_frame_counts[tid] >= 3:
                self._confirmed_track_ids.add(tid)

            # Identity lookup
            identity = self._identities.get(tid)
            if identity:
                state = "confirmed"
            elif tid in self._confirmed_track_ids:
                state = "unknown"
            else:
                state = "new"

            result.append({
                "bbox": tuple(int(v) for v in bbox),
                "name": identity["name"] if identity else None,
                "student_id": identity.get("student_id") if identity else None,
                "confidence": identity["confidence"] if identity else 0.0,
                "track_state": state,
                "track_id": tid,
                "duration_sec": now - self._track_start_times[tid],
            })
        return result

    def start(self) -> None:
        """Initialize all components and enter the processing loop."""
        cfg = self.config
        w, h, fps = cfg["width"], cfg["height"], cfg["fps"]

        logger.info(f"[Pipeline:{self.room_id}] Starting — {w}x{h}@{fps}fps")

        # RTSP reader
        self._reader = RTSPReader(cfg["rtsp_source"], target_fps=fps)
        self._reader.start()

        # FFmpeg publisher
        self._publisher = FFmpegPublisher(cfg["rtsp_target"], w, h, fps)
        self._publisher.start()

        # Annotator
        self._annotator = FrameAnnotator(w, h)

        # ByteTrack
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.20,
            lost_track_buffer=90,
            minimum_matching_threshold=0.7,
            frame_rate=fps,
            minimum_consecutive_frames=3,
        )

        # ML models (deferred import to avoid loading at module level)
        try:
            from app.services.ml.faiss_manager import faiss_manager
            from app.services.ml.insightface_model import insightface_model

            if not insightface_model._model_loaded:
                insightface_model.load_model()
            self._detector = insightface_model
            self._faiss = faiss_manager
        except Exception as e:
            logger.error(f"[Pipeline:{self.room_id}] ML model load failed: {e}")

        self._running = True
        self._run_loop()

    def _run_loop(self) -> None:
        """Main processing loop — read, detect, track, recognize, annotate, publish."""
        cfg = self.config
        frame_interval = 1.0 / cfg["fps"]
        last_state_push = 0.0
        last_recognition_check = 0.0

        while self._running:
            loop_start = time.time()

            # Read latest frame
            frame = self._reader.read() if self._reader else None
            if frame is None:
                time.sleep(0.1)
                continue

            # Resize if needed
            h, w = frame.shape[:2]
            target_w, target_h = cfg["width"], cfg["height"]
            if w != target_w or h != target_h:
                frame = cv2.resize(frame, (target_w, target_h))

            # Detect faces
            detections = self._detect_faces(frame)

            # Track
            tracked = self._tracker.update_with_detections(detections)

            # Recognize new/unidentified tracks
            now = time.time()
            if now - last_recognition_check > 0.2:  # Max 5 recognition batches/sec
                self._recognize_new_tracks(frame, tracked)
                last_recognition_check = now

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

    def _detect_faces(self, frame: np.ndarray) -> sv.Detections:
        """Run SCRFD face detection on frame."""
        if self._detector is None:
            return sv.Detections.empty()

        try:
            faces = self._detector.get_faces(frame)
            if not faces:
                return sv.Detections.empty()

            bboxes = np.array([f.bbox for f in faces], dtype=np.float32)
            scores = np.array([f.det_score for f in faces], dtype=np.float32)
            return sv.Detections(xyxy=bboxes, confidence=scores)
        except Exception as e:
            logger.error(f"[Pipeline:{self.room_id}] Detection error: {e}")
            return sv.Detections.empty()

    def _recognize_new_tracks(self, frame: np.ndarray, tracked: sv.Detections) -> None:
        """Run ArcFace recognition on new/unidentified confirmed tracks."""
        if self._detector is None or self._faiss is None:
            return
        if tracked.tracker_id is None:
            return

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            # Skip already identified or unconfirmed tracks
            if tid in self._identities or tid not in self._confirmed_track_ids:
                continue

            try:
                x1, y1, x2, y2 = [int(v) for v in tracked.xyxy[i]]
                # Pad crop by 20%
                bw, bh = x2 - x1, y2 - y1
                pad_x, pad_y = int(bw * 0.2), int(bh * 0.2)
                cx1 = max(0, x1 - pad_x)
                cy1 = max(0, y1 - pad_y)
                cx2 = min(frame.shape[1], x2 + pad_x)
                cy2 = min(frame.shape[0], y2 + pad_y)
                crop = frame[cy1:cy2, cx1:cx2]

                if crop.size == 0:
                    continue

                embedding = self._detector.get_embedding(crop)
                if embedding is None:
                    continue

                match = self._faiss.search_with_margin(
                    embedding,
                    k=settings.RECOGNITION_TOP_K,
                    threshold=settings.RECOGNITION_THRESHOLD,
                    margin=settings.RECOGNITION_MARGIN,
                )
                if match and not match.get("is_ambiguous", False):
                    self._identities[tid] = {
                        "user_id": match["user_id"],
                        "name": match.get("name", "Unknown"),
                        "student_id": match.get("student_id", ""),
                        "confidence": match["confidence"],
                    }
                    logger.info(
                        f"[Pipeline:{self.room_id}] Track {tid} → "
                        f"{match.get('name')} ({match['confidence']:.2f})"
                    )
            except Exception as e:
                logger.debug(f"[Pipeline:{self.room_id}] Recognition error for track {tid}: {e}")

    def _cleanup_stale_tracks(self, tracked: sv.Detections) -> None:
        """Remove identities and state for tracks no longer active."""
        active_ids = set()
        if tracked.tracker_id is not None:
            active_ids = {int(tid) for tid in tracked.tracker_id}

        stale = set(self._track_start_times.keys()) - active_ids
        for tid in stale:
            self._identities.pop(tid, None)
            self._track_start_times.pop(tid, None)
            self._track_frame_counts.pop(tid, None)
            self._confirmed_track_ids.discard(tid)

    def _publish_state_to_redis(self, det_list: list[dict]) -> None:
        """Publish current pipeline state to Redis for FastAPI to read."""
        try:
            identified = [d for d in det_list if d["name"] is not None]
            state = {
                "ts": time.time(),
                "room_id": self.room_id,
                "total_tracks": len(det_list),
                "identified_count": len(identified),
                "identified_users": [
                    {"user_id": d.get("user_id", self._identities.get(d["track_id"], {}).get("user_id")),
                     "name": d["name"],
                     "confidence": d["confidence"]}
                    for d in identified
                ],
                "status": "running",
            }
            self._redis.set(
                f"pipeline:{self.room_id}:state",
                json.dumps(state),
                ex=30,
            )
            self._redis.set(
                f"pipeline:{self.room_id}:heartbeat",
                json.dumps({"ts": time.time(), "status": "running"}),
                ex=30,
            )
        except Exception as e:
            logger.debug(f"[Pipeline:{self.room_id}] Redis publish error: {e}")

    def _restart_publisher(self) -> None:
        """Restart FFmpeg publisher on failure."""
        if self._publisher:
            self._publisher.stop()
            time.sleep(1)
            self._publisher.start()

    def stop(self) -> None:
        """Stop all pipeline components."""
        self._running = False
        logger.info(f"[Pipeline:{self.room_id}] Stopping...")
        if self._reader:
            self._reader.stop()
        if self._publisher:
            self._publisher.stop()

    def update_hud(self, **kwargs) -> None:
        """Update HUD info (called by FastAPI when session state changes)."""
        self._hud_info.update(kwargs)
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_video_pipeline.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/app/pipeline/video_pipeline.py backend/tests/test_pipeline/test_video_pipeline.py
git commit -m "feat: add VideoAnalyticsPipeline — unified detect/track/recognize/annotate"
```

---

### Task 6: Create PipelineManager — lifecycle management

**Files:**
- Create: `backend/app/pipeline/pipeline_manager.py`
- Test: `backend/tests/test_pipeline/test_pipeline_manager.py`

**Step 1: Write the failing test**

Create `backend/tests/test_pipeline/test_pipeline_manager.py`:

```python
"""Tests for PipelineManager — manages pipeline lifecycle."""

from unittest.mock import MagicMock, patch

import pytest


class TestPipelineManager:
    def test_start_pipeline_creates_process(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        with patch("app.pipeline.pipeline_manager.multiprocessing") as mock_mp:
            mock_proc = MagicMock()
            mock_mp.Process.return_value = mock_proc

            mgr.start_pipeline({
                "room_id": "room-1",
                "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
                "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
                "width": 640, "height": 480, "fps": 25,
                "room_name": "R301", "det_model": "buffalo_sc",
            })
            assert "room-1" in mgr._pipelines
            mock_proc.start.assert_called_once()

    def test_stop_pipeline_terminates_process(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = True
        mgr._pipelines["room-1"] = {"process": mock_proc, "config": {}}

        mgr.stop_pipeline("room-1")
        mock_proc.terminate.assert_called_once()
        assert "room-1" not in mgr._pipelines

    def test_stop_nonexistent_pipeline_is_noop(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mgr.stop_pipeline("nonexistent")  # Should not raise

    def test_get_status_returns_all_pipelines(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = True
        mock_proc.pid = 12345
        mgr._pipelines["room-1"] = {"process": mock_proc, "config": {"room_id": "room-1"}}

        status = mgr.get_status()
        assert len(status) == 1
        assert status[0]["room_id"] == "room-1"
        assert status[0]["alive"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_pipeline_manager.py -v`
Expected: FAIL

**Step 3: Write PipelineManager**

Create `backend/app/pipeline/pipeline_manager.py`:

```python
"""Pipeline lifecycle manager — starts, stops, and monitors video pipelines.

Each pipeline runs as a separate process for CPU isolation from FastAPI.
Communication happens via Redis (state publishing + commands).
"""

import multiprocessing
import time

from app.config import logger


def _run_pipeline_process(config: dict, redis_url: str) -> None:
    """Entry point for the pipeline subprocess."""
    import redis as redis_lib

    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    pipeline = VideoAnalyticsPipeline(config)
    pipeline._redis = redis_lib.Redis.from_url(redis_url)

    try:
        pipeline.start()  # Blocking loop
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"[Pipeline:{config['room_id']}] Crashed: {e}")
    finally:
        pipeline.stop()


class PipelineManager:
    """Manages video pipeline processes."""

    def __init__(self, redis_url: str = "redis://redis:6379/0"):
        self._pipelines: dict[str, dict] = {}
        self._redis_url = redis_url

    def start_pipeline(self, config: dict) -> None:
        """Start a pipeline for a room."""
        room_id = config["room_id"]

        if room_id in self._pipelines:
            proc = self._pipelines[room_id]["process"]
            if proc.is_alive():
                logger.warning(f"Pipeline for {room_id} already running")
                return
            # Dead process — clean up and restart
            self._pipelines.pop(room_id)

        proc = multiprocessing.Process(
            target=_run_pipeline_process,
            args=(config, self._redis_url),
            daemon=True,
            name=f"pipeline-{room_id}",
        )
        proc.start()
        self._pipelines[room_id] = {"process": proc, "config": config}
        logger.info(f"Pipeline for {room_id} started (PID {proc.pid})")

    def stop_pipeline(self, room_id: str) -> None:
        """Stop a pipeline for a room."""
        entry = self._pipelines.pop(room_id, None)
        if entry is None:
            return

        proc = entry["process"]
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=10)
            if proc.is_alive():
                proc.kill()
        logger.info(f"Pipeline for {room_id} stopped")

    def stop_all(self) -> None:
        """Stop all running pipelines."""
        for room_id in list(self._pipelines.keys()):
            self.stop_pipeline(room_id)

    def get_status(self) -> list[dict]:
        """Get status of all pipelines."""
        result = []
        for room_id, entry in self._pipelines.items():
            proc = entry["process"]
            result.append({
                "room_id": room_id,
                "alive": proc.is_alive(),
                "pid": proc.pid,
            })
        return result

    def check_health(self) -> None:
        """Restart any dead pipelines."""
        for room_id, entry in list(self._pipelines.items()):
            proc = entry["process"]
            if not proc.is_alive():
                logger.warning(f"Pipeline for {room_id} died, restarting...")
                self._pipelines.pop(room_id)
                self.start_pipeline(entry["config"])
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_pipeline/test_pipeline_manager.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/pipeline/pipeline_manager.py backend/tests/test_pipeline/test_pipeline_manager.py
git commit -m "feat: add PipelineManager for video pipeline lifecycle"
```

---

## Phase 2: Wire Pipeline Into FastAPI

### Task 7: Update main.py startup/shutdown

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py` (add pipeline config settings)

**Step 1: Add pipeline config settings**

In `backend/app/config.py`, add to the `Settings` class after the existing presence tracking section:

```python
    # Video Pipeline
    PIPELINE_ENABLED: bool = True
    PIPELINE_FPS: int = 25
    PIPELINE_WIDTH: int = 640
    PIPELINE_HEIGHT: int = 480
    PIPELINE_DET_MODEL: str = "buffalo_sc"
    MEDIAMTX_RTSP_URL: str = "rtsp://mediamtx:8554"
```

**Step 2: Replace TrackFusionEngine startup with PipelineManager**

In `backend/app/main.py`, replace the TrackFusionEngine startup block (lines ~183-191) with:

```python
    # ── Video Pipeline Manager ──────────────────────────────────────
    if settings.PIPELINE_ENABLED:
        try:
            from app.pipeline.pipeline_manager import PipelineManager

            pipeline_manager = PipelineManager(
                redis_url=settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else "redis://redis:6379/0"
            )
            app.state.pipeline_manager = pipeline_manager
            logger.info("PipelineManager initialized (pipelines start on session start)")
        except Exception as e:
            logger.error(f"Failed to initialize PipelineManager: {e}")
```

Replace the TrackFusionEngine shutdown block with:

```python
    # Stop Pipeline Manager
    if hasattr(app.state, "pipeline_manager"):
        try:
            app.state.pipeline_manager.stop_all()
            logger.info("All video pipelines stopped")
        except Exception as e:
            logger.error(f"Failed to stop pipelines: {e}")
```

**Step 3: Verify the app still starts**

Run: `cd backend && python -c "from app.main import app; print('App created OK')"`
Expected: "App created OK"

**Step 4: Commit**

```bash
git add backend/app/main.py backend/app/config.py
git commit -m "feat: wire PipelineManager into FastAPI startup/shutdown"
```

---

### Task 8: Update presence_service to read from pipeline Redis state

**Files:**
- Modify: `backend/app/services/presence_service.py`

**Step 1: Replace TrackFusionEngine dependency**

In `presence_service.py`, replace the import:
```python
from app.services.track_fusion_service import get_track_fusion_engine
```

With a Redis-based reader:
```python
import json
import redis as redis_lib
```

**Step 2: Update `process_session_scan` method**

Replace the call to `get_track_fusion_engine().get_identified_users(room_id)` with a Redis read:

```python
def _get_identified_users_from_pipeline(self, room_id: str) -> list[dict]:
    """Read identified users from the video pipeline's Redis state."""
    try:
        r = redis_lib.Redis.from_url(
            settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else "redis://redis:6379/0"
        )
        raw = r.get(f"pipeline:{room_id}:state")
        if raw is None:
            return []
        state = json.loads(raw)
        return state.get("identified_users", [])
    except Exception as e:
        logger.error(f"Failed to read pipeline state for {room_id}: {e}")
        return []
```

**Step 3: Commit**

```bash
git add backend/app/services/presence_service.py
git commit -m "feat: presence service reads from pipeline Redis state instead of TrackFusionEngine"
```

---

### Task 9: Add pipeline management API endpoint

**Files:**
- Create: `backend/app/routers/pipeline.py`
- Modify: `backend/app/main.py` (add router)

**Step 1: Create pipeline router**

Create `backend/app/routers/pipeline.py`:

```python
"""Pipeline management API — start/stop/status for video analytics pipelines."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.utils.dependencies import get_current_user

router = APIRouter()


class PipelineStartRequest(BaseModel):
    room_id: str
    room_name: str = ""
    subject: str = ""
    professor: str = ""
    total_enrolled: int = 0
    schedule_id: str | None = None


class PipelineStatusResponse(BaseModel):
    room_id: str
    alive: bool
    pid: int | None = None


@router.post("/start")
async def start_pipeline(req: PipelineStartRequest, request: Request):
    """Start a video analytics pipeline for a room."""
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        raise HTTPException(503, "Pipeline manager not initialized")

    config = {
        "room_id": req.room_id,
        "rtsp_source": f"{settings.MEDIAMTX_RTSP_URL}/{req.room_id}/raw",
        "rtsp_target": f"{settings.MEDIAMTX_RTSP_URL}/{req.room_id}/annotated",
        "width": settings.PIPELINE_WIDTH,
        "height": settings.PIPELINE_HEIGHT,
        "fps": settings.PIPELINE_FPS,
        "room_name": req.room_name,
        "subject": req.subject,
        "professor": req.professor,
        "total_enrolled": req.total_enrolled,
        "det_model": settings.PIPELINE_DET_MODEL,
    }
    mgr.start_pipeline(config)
    return {"status": "started", "room_id": req.room_id}


@router.post("/stop/{room_id}")
async def stop_pipeline(room_id: str, request: Request):
    """Stop a video analytics pipeline."""
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        raise HTTPException(503, "Pipeline manager not initialized")

    mgr.stop_pipeline(room_id)
    return {"status": "stopped", "room_id": room_id}


@router.get("/status", response_model=list[PipelineStatusResponse])
async def pipeline_status(request: Request):
    """Get status of all running pipelines."""
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        return []
    return mgr.get_status()
```

**Step 2: Register router in main.py**

Add to imports and router includes in `backend/app/main.py`:
```python
from app.routers import pipeline
# ...
app.include_router(pipeline.router, prefix=f"{settings.API_PREFIX}/pipeline", tags=["Pipeline"])
```

**Step 3: Commit**

```bash
git add backend/app/routers/pipeline.py backend/app/main.py
git commit -m "feat: add pipeline management API endpoints"
```

---

## Phase 3: Update Docker Compose

### Task 10: Simplify docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Remove detection-worker and recognition-worker services**

Delete the `detection-worker` and `recognition-worker` service blocks (lines 49-89 in current file).

**Step 2: Update api-gateway resource allocation**

The api-gateway now runs the PipelineManager which spawns pipeline processes. It needs access to the FAISS data and InsightFace models:

```yaml
  api-gateway:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: iams-api-gateway
    env_file:
      - ./backend/.env
    environment:
      - SERVICE_ROLE=api-gateway
      - REDIS_URL=redis://redis:6379/0
      - MEDIAMTX_EXTERNAL=true
      - MEDIAMTX_API_URL=http://mediamtx:9997
      - MEDIAMTX_WEBRTC_URL=http://mediamtx:8889
      - MEDIAMTX_RTSP_URL=rtsp://mediamtx:8554
      - EDGE_API_KEY=iams-edge-key-2026-prod
      - PIPELINE_ENABLED=true
    volumes:
      - ./backend:/app
      - faiss_data:/app/data/faiss
      - face_uploads:/app/data/uploads/faces
      - insightface_models:/root/.insightface/models
      - app_logs:/app/logs
    ports:
      - "8000:8000"
    command: >
      uvicorn app.main:app
      --host 0.0.0.0 --port 8000
      --reload --reload-dir /app/app
    depends_on:
      mediamtx:
        condition: service_started
      redis:
        condition: service_healthy
    restart: unless-stopped
```

**Step 3: Verify compose file is valid**

Run: `cd /Users/cjjutba/Projects/iams && docker compose config --quiet`
Expected: No errors

**Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: remove detection/recognition workers from docker-compose"
```

---

## Phase 4: Clean Up Old Architecture

### Task 11: Remove old workers and TrackFusionEngine

**Files:**
- Delete: `backend/app/workers/detection_worker.py`
- Delete: `backend/app/workers/recognition_worker.py`
- Delete: `backend/app/services/track_fusion_service.py`
- Delete: `backend/app/routers/live_stream.py` (detection metadata WebSocket)
- Modify: `backend/app/main.py` (remove dead imports and router)

**Step 1: Remove files**

```bash
cd /Users/cjjutba/Projects/iams/backend
rm app/workers/detection_worker.py
rm app/workers/recognition_worker.py
rm app/services/track_fusion_service.py
rm app/routers/live_stream.py
```

**Step 2: Update main.py**

Remove the import of `live_stream` from the router imports. Remove the `live_stream` router include line. Remove any remaining TrackFusionEngine references.

**Step 3: Update edge_ws.py**

The edge WebSocket frame ingest (`edge_ws.py`) is no longer needed for the pipeline. It can be kept temporarily for backward compatibility or removed. For now, mark it as deprecated — the RPi no longer sends frames via WebSocket.

**Step 4: Commit**

```bash
git add -A backend/app/workers/ backend/app/services/ backend/app/routers/ backend/app/main.py
git commit -m "refactor: remove old workers, TrackFusionEngine, and live_stream router"
```

---

### Task 12: Simplify edge device

**Files:**
- Delete: `edge/app/frame_sampler.py`
- Rewrite: `edge/app/main.py`
- Simplify: `edge/app/config.py`
- Modify: `edge/requirements.txt`

**Step 1: Delete frame_sampler**

```bash
rm /Users/cjjutba/Projects/iams/edge/app/frame_sampler.py
```

**Step 2: Simplify config.py**

Rewrite `edge/app/config.py` to remove WebSocket, sampling, and queue settings:

```python
"""RPi Camera Gateway configuration — RTSP relay only."""
import os
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

# Reolink P340 RTSP URLs
CAMERA_IP = os.getenv("CAMERA_IP", "192.168.1.100")
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASS = os.getenv("CAMERA_PASS", "password")
_PASS_ENC = quote(CAMERA_PASS, safe="")
RTSP_SUB = f"rtsp://{CAMERA_USER}:{_PASS_ENC}@{CAMERA_IP}:554/h264Preview_01_sub"

# VPS mediamtx target
VPS_HOST = os.getenv("VPS_HOST", "167.71.217.44")
VPS_RTSP_URL = f"rtsp://{VPS_HOST}:8554"
ROOM_ID = os.getenv("ROOM_ID", "room-1")
```

**Step 3: Rewrite main.py**

```python
"""RPi Camera Gateway — relays Reolink RTSP to VPS mediamtx.

That's all it does. No ML, no frame sampling, no WebSocket.
"""
import signal
import sys
import time

from app.config import ROOM_ID, RTSP_SUB, VPS_RTSP_URL
from app.stream_relay import StreamRelay


def main():
    relay = StreamRelay(RTSP_SUB, f"{VPS_RTSP_URL}/{ROOM_ID}/raw")

    def shutdown(signum, frame):
        print(f"Received signal {signum}, stopping...")
        relay.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Starting RTSP relay: {RTSP_SUB} → {VPS_RTSP_URL}/{ROOM_ID}/raw")
    relay.start()

    # Keep main thread alive
    try:
        while True:
            if not relay.is_alive():
                print("Relay died, restarting...")
                relay.start()
            time.sleep(5)
    except KeyboardInterrupt:
        relay.stop()


if __name__ == "__main__":
    main()
```

**Step 4: Simplify requirements.txt**

```
psutil>=5.9
python-dotenv>=1.0
```

Remove `opencv-python-headless` and `websockets`.

**Step 5: Commit**

```bash
git add -A edge/
git commit -m "refactor: simplify edge device to pure RTSP relay"
```

---

## Phase 5: Simplify Mobile App

### Task 13: Remove overlay components

**Files:**
- Delete: `mobile/src/components/video/DetectionOverlay.tsx`
- Delete: `mobile/src/engines/TrackAnimationEngine.ts`
- Delete: `mobile/src/hooks/useDetectionTracker.ts`

**Step 1: Remove files**

```bash
cd /Users/cjjutba/Projects/iams/mobile
rm src/components/video/DetectionOverlay.tsx
rm src/engines/TrackAnimationEngine.ts
rm src/hooks/useDetectionTracker.ts
```

**Step 2: Commit**

```bash
git add -A mobile/src/components/video/ mobile/src/engines/ mobile/src/hooks/
git commit -m "refactor: remove DetectionOverlay, TrackAnimationEngine, useDetectionTracker"
```

---

### Task 14: Simplify FacultyLiveFeedScreen

**Files:**
- Modify: `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx`
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts`

**Step 1: Simplify useDetectionWebSocket**

The detection WebSocket no longer sends fused_tracks. Simplify it to only handle connection status and session state. Remove all track parsing, studentMap, and coordinate conversion logic. It only needs to:
- Connect to the stream WebSocket
- Handle "connected" message (to know stream mode)
- Handle "session_start" / "session_end" messages
- Handle attendance count updates

**Step 2: Simplify FacultyLiveFeedScreen**

Remove:
- `FusedDetectionOverlay` import and rendering
- `computeScale` calculations
- `containerWidth` / `containerHeight` tracking via `onLayout`
- `isComposited` logic (it's always composited now)

The screen becomes:
```tsx
<View style={styles.container}>
  <Header />
  <StatusBar />
  <View style={styles.feedContainer}>
    <RTCView
      streamURL={remoteStream?.toURL()}
      style={StyleSheet.absoluteFillObject}
      objectFit="contain"
    />
  </View>
  <AttendancePanel />
</View>
```

**Step 3: Update useWebRTC to point to annotated stream**

The WebRTC offer endpoint stays the same — the backend's `webrtc` router needs to proxy to the annotated stream path instead of the raw path. Update `backend/app/services/webrtc_service.py` or `backend/app/routers/webrtc.py` to use `{room_id}/annotated` as the mediamtx stream path.

**Step 4: Commit**

```bash
git add mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx
git add mobile/src/hooks/useDetectionWebSocket.ts
git add backend/app/routers/webrtc.py
git commit -m "refactor: simplify mobile live feed — remove overlay, just play annotated WebRTC"
```

---

## Phase 6: Integration Test

### Task 15: End-to-end pipeline test with mediamtx

**Files:**
- Create: `backend/tests/test_pipeline/test_integration.py`

**Step 1: Write integration test**

This test requires Docker (mediamtx + Redis running). Mark it with `@pytest.mark.integration`:

```python
"""Integration test — verify pipeline reads RTSP, processes, and publishes."""
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.mark.integration
class TestPipelineIntegration:
    def test_pipeline_manager_starts_and_stops(self):
        """Verify PipelineManager can start and stop a pipeline process."""
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager(redis_url="redis://localhost:6379/0")
        config = {
            "room_id": "test-room",
            "rtsp_source": "rtsp://localhost:8554/test/raw",
            "rtsp_target": "rtsp://localhost:8554/test/annotated",
            "width": 640, "height": 480, "fps": 15,
            "room_name": "Test Room", "det_model": "buffalo_sc",
            "subject": "Test", "professor": "Prof. Test",
            "total_enrolled": 10,
        }
        mgr.start_pipeline(config)
        time.sleep(2)

        status = mgr.get_status()
        assert len(status) == 1
        assert status[0]["room_id"] == "test-room"

        mgr.stop_pipeline("test-room")
        assert len(mgr.get_status()) == 0
```

**Step 2: Run integration test (requires Docker stack)**

Run: `cd backend && python -m pytest tests/test_pipeline/test_integration.py -v -m integration`

**Step 3: Commit**

```bash
git add backend/tests/test_pipeline/test_integration.py
git commit -m "test: add pipeline integration test"
```

---

## Phase 7: Final Verification

### Task 16: Full stack smoke test

**Step 1: Start the stack**

```bash
./scripts/dev-up.sh
```

**Step 2: Verify containers are healthy**

```bash
docker compose ps
```
Expected: `api-gateway`, `redis`, `mediamtx` all running. No `detection-worker` or `recognition-worker`.

**Step 3: Start a pipeline via API**

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{"room_id": "room-1", "room_name": "Room 301", "subject": "CS101", "professor": "Prof. Santos", "total_enrolled": 35}'
```
Expected: `{"status": "started", "room_id": "room-1"}`

**Step 4: Check pipeline status**

```bash
curl http://localhost:8000/api/v1/pipeline/status
```
Expected: `[{"room_id": "room-1", "alive": true, "pid": ...}]`

**Step 5: Verify annotated stream in mediamtx**

```bash
curl http://localhost:9997/v3/paths/list | python -m json.tool
```
Expected: Shows `room-1/annotated` path (once the pipeline connects)

**Step 6: Open mobile app**

Navigate to the Faculty Live Feed screen. It should show the annotated WebRTC stream with bounding boxes burned into the video.

**Step 7: Commit final state**

```bash
git add -A
git commit -m "feat: complete RTSP-direct server-side compositing architecture"
```

---

## Summary: File Inventory

### New files
```
backend/app/pipeline/__init__.py
backend/app/pipeline/rtsp_reader.py
backend/app/pipeline/ffmpeg_publisher.py
backend/app/pipeline/frame_annotator.py
backend/app/pipeline/video_pipeline.py
backend/app/pipeline/pipeline_manager.py
backend/app/routers/pipeline.py
backend/tests/test_pipeline/__init__.py
backend/tests/test_pipeline/test_rtsp_reader.py
backend/tests/test_pipeline/test_frame_annotator.py
backend/tests/test_pipeline/test_ffmpeg_publisher.py
backend/tests/test_pipeline/test_video_pipeline.py
backend/tests/test_pipeline/test_pipeline_manager.py
backend/tests/test_pipeline/test_integration.py
```

### Deleted files
```
backend/app/workers/detection_worker.py
backend/app/workers/recognition_worker.py
backend/app/services/track_fusion_service.py
backend/app/routers/live_stream.py
edge/app/frame_sampler.py
mobile/src/components/video/DetectionOverlay.tsx
mobile/src/engines/TrackAnimationEngine.ts
mobile/src/hooks/useDetectionTracker.ts
```

### Modified files
```
backend/requirements.txt (add supervision)
backend/app/config.py (add pipeline settings)
backend/app/main.py (PipelineManager instead of TrackFusionEngine)
backend/app/services/presence_service.py (Redis read instead of TrackFusion)
backend/app/routers/webrtc.py (point to annotated stream)
docker-compose.yml (remove worker containers)
edge/app/config.py (simplify)
edge/app/main.py (rewrite to relay-only)
edge/requirements.txt (remove opencv, websockets)
mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx (remove overlay)
mobile/src/hooks/useDetectionWebSocket.ts (simplify)
```
