"""
Unit tests for FrameGrabber — persistent RTSP frame source.

cv2.VideoCapture is mocked throughout; no real RTSP connection is needed.
"""

import threading
import time

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


RTSP_URL = "rtsp://192.168.1.100:8554/cam1"


def _make_fake_frame(value: int = 42) -> np.ndarray:
    """Return a small 4x4 BGR frame filled with *value*."""
    return np.full((4, 4, 3), value, dtype=np.uint8)


@pytest.fixture
def mock_cap():
    """A mock cv2.VideoCapture that reads one fake frame then blocks."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.read.return_value = (True, _make_fake_frame(42))
    cap.release = MagicMock()
    return cap


@pytest.fixture
def grabber(mock_cap):
    """A FrameGrabber wired to the mock capture, auto-stopped after test."""
    with patch("cv2.VideoCapture", return_value=mock_cap):
        from app.services.frame_grabber import FrameGrabber
        fg = FrameGrabber(RTSP_URL, stale_timeout=30.0)
        yield fg
        fg.stop()


# ---------------------------------------------------------------------------
# grab() returns None before first frame
# ---------------------------------------------------------------------------

def test_grab_returns_none_before_first_frame():
    """grab() must return None when no frame has been received yet."""
    from app.services.frame_grabber import FrameGrabber

    cap = MagicMock()
    cap.isOpened.return_value = True
    # read() blocks indefinitely (never returns a frame)
    cap.read.side_effect = lambda: (False, None)

    with patch("cv2.VideoCapture", return_value=cap):
        fg = FrameGrabber(RTSP_URL)
        try:
            # Give drain thread a moment to start (but it will get no frames)
            time.sleep(0.05)
            assert fg.grab() is None
        finally:
            fg.stop()


# ---------------------------------------------------------------------------
# grab() returns the latest frame after drain loop runs
# ---------------------------------------------------------------------------

def test_grab_returns_latest_frame(grabber, mock_cap):
    """After the drain loop reads a frame, grab() must return it."""
    # Give drain thread time to read at least one frame
    time.sleep(0.1)
    frame = grabber.grab()
    assert frame is not None
    assert frame.shape == (4, 4, 3)
    assert frame.dtype == np.uint8
    np.testing.assert_array_equal(frame, _make_fake_frame(42))


# ---------------------------------------------------------------------------
# grab() returns a copy (not a reference)
# ---------------------------------------------------------------------------

def test_grab_returns_copy_not_reference(grabber):
    """Two consecutive grab() calls must return independent arrays."""
    time.sleep(0.1)
    frame_a = grabber.grab()
    frame_b = grabber.grab()
    assert frame_a is not None
    assert frame_b is not None
    # They should be equal in content...
    np.testing.assert_array_equal(frame_a, frame_b)
    # ...but NOT the same object in memory
    assert frame_a is not frame_b
    # Mutating one must not affect the other
    frame_a[0, 0, 0] = 255
    assert frame_b[0, 0, 0] != 255


# ---------------------------------------------------------------------------
# grab() returns None and triggers reconnect when frame is stale
# ---------------------------------------------------------------------------

def test_grab_returns_none_when_stale_and_reconnects():
    """When the last frame is older than stale_timeout, grab() must return
    None and trigger a reconnect (new VideoCapture)."""
    from app.services.frame_grabber import FrameGrabber

    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.read.return_value = (True, _make_fake_frame(99))

    vc_calls = []

    def make_cap(*args, **kwargs):
        c = MagicMock()
        c.isOpened.return_value = True
        c.read.return_value = (True, _make_fake_frame(99))
        vc_calls.append(c)
        return c

    with patch("cv2.VideoCapture", side_effect=make_cap):
        fg = FrameGrabber(RTSP_URL, stale_timeout=0.1)
        try:
            # Let drain thread populate a frame
            time.sleep(0.15)
            assert fg.grab() is not None

            # Now simulate staleness: stop the drain thread from updating
            # by making read() block (return False)
            for c in vc_calls:
                c.read.return_value = (False, None)

            # Wait for stale_timeout to expire
            time.sleep(0.3)

            # grab() should detect staleness and return None
            frame = fg.grab()
            assert frame is None

            # A reconnect should have been triggered (more VideoCapture calls)
            assert len(vc_calls) > 1
        finally:
            fg.stop()


# ---------------------------------------------------------------------------
# Thread safety under concurrent access
# ---------------------------------------------------------------------------

def test_thread_safety_concurrent_reads(grabber):
    """4 threads x 100 reads must not crash or corrupt data."""
    time.sleep(0.1)  # let drain loop populate a frame

    errors = []

    def reader():
        for _ in range(100):
            try:
                frame = grabber.grab()
                if frame is not None:
                    # Validate shape hasn't been corrupted
                    assert frame.shape == (4, 4, 3)
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(errors) == 0, f"Concurrent reads raised errors: {errors}"


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


def test_stop_releases_capture(grabber, mock_cap):
    """stop() must call release() on the VideoCapture."""
    grabber.stop()
    mock_cap.release.assert_called()
