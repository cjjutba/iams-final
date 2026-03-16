"""Tests for RTSPReader -- threaded RTSP capture with latest-frame semantics."""

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
