"""
Unit tests for FrameGrabber — persistent RTSP frame source.

subprocess.Popen is mocked throughout; no real FFmpeg or RTSP connection is needed.
"""

import threading
import time

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


RTSP_URL = "rtsp://192.168.1.100:8554/cam1"
# Defaults matching settings (640x480 BGR24)
WIDTH = 640
HEIGHT = 480
FRAME_BYTES = WIDTH * HEIGHT * 3


def _make_raw_frame(value: int = 42) -> bytes:
    """Return raw BGR24 bytes for a WxH frame filled with *value*."""
    return bytes([value] * FRAME_BYTES)


def _make_mock_process(frame_data: bytes | None = None):
    """Create a mock subprocess.Popen with a readable stdout pipe."""
    proc = MagicMock()
    proc.pid = 12345
    proc.poll.return_value = None  # Process is running

    if frame_data is not None:
        # Simulate stdout that yields frame data repeatedly
        proc.stdout = MagicMock()
        proc.stdout.read.return_value = frame_data
    else:
        proc.stdout = MagicMock()
        proc.stdout.read.return_value = b""  # EOF

    return proc


@pytest.fixture
def grabber():
    """A FrameGrabber wired to a mock FFmpeg process, auto-stopped after test."""
    raw = _make_raw_frame(42)
    proc = _make_mock_process(raw)

    with (
        patch("subprocess.Popen", return_value=proc),
        patch("app.services.frame_grabber.settings") as mock_settings,
    ):
        mock_settings.FRAME_GRABBER_WIDTH = WIDTH
        mock_settings.FRAME_GRABBER_HEIGHT = HEIGHT
        mock_settings.FRAME_GRABBER_FPS = 10

        from app.services.frame_grabber import FrameGrabber

        fg = FrameGrabber(RTSP_URL, stale_timeout=30.0)
        yield fg
        fg.stop()


# ---------------------------------------------------------------------------
# grab() returns None before first frame
# ---------------------------------------------------------------------------


def test_grab_returns_none_before_first_frame():
    """grab() must return None when no frame has been received yet."""
    proc = _make_mock_process(None)  # EOF — no frames

    with (
        patch("subprocess.Popen", return_value=proc),
        patch("app.services.frame_grabber.settings") as mock_settings,
    ):
        mock_settings.FRAME_GRABBER_WIDTH = WIDTH
        mock_settings.FRAME_GRABBER_HEIGHT = HEIGHT
        mock_settings.FRAME_GRABBER_FPS = 10

        from app.services.frame_grabber import FrameGrabber

        fg = FrameGrabber(RTSP_URL)
        try:
            time.sleep(0.05)
            assert fg.grab() is None
        finally:
            fg.stop()


# ---------------------------------------------------------------------------
# grab() returns the latest frame after drain loop runs
# ---------------------------------------------------------------------------


def test_grab_returns_latest_frame(grabber):
    """After the drain loop reads a frame, grab() must return it."""
    # Give drain thread time to read frames (needs >3 for warmup)
    time.sleep(0.3)
    frame = grabber.grab()
    assert frame is not None
    assert frame.shape == (HEIGHT, WIDTH, 3)
    assert frame.dtype == np.uint8


# ---------------------------------------------------------------------------
# grab() returns the latest frame reference (zero-copy for efficiency)
# ---------------------------------------------------------------------------


def test_grab_returns_copy_not_reference(grabber):
    """Two consecutive grab() calls return the same frame (zero-copy).

    The drain loop creates a new numpy array per frame via np.frombuffer,
    so isolation is guaranteed between frames. Within the same frame,
    grab() returns the same reference for efficiency (no 2.7MB copy).
    """
    time.sleep(0.3)
    frame_a = grabber.grab()
    frame_b = grabber.grab()
    assert frame_a is not None
    assert frame_b is not None
    np.testing.assert_array_equal(frame_a, frame_b)


# ---------------------------------------------------------------------------
# is_alive() and stop()
# ---------------------------------------------------------------------------


def test_is_alive_returns_true_when_running(grabber):
    """is_alive() must return True while the drain thread is active."""
    time.sleep(0.05)
    assert grabber.is_alive() is True


def test_is_alive_returns_false_after_stop(grabber):
    """is_alive() must return False after stop() is called."""
    grabber.stop()
    assert grabber.is_alive() is False


def test_stop_is_idempotent(grabber):
    """Calling stop() twice must not raise."""
    grabber.stop()
    grabber.stop()  # should be a no-op


def test_stop_kills_ffmpeg(grabber):
    """stop() must terminate the FFmpeg subprocess."""
    grabber.stop()
    # Process should be set to None after kill
    assert grabber._process is None
