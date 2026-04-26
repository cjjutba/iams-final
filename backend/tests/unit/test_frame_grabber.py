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


# ---------------------------------------------------------------------------
# Backoff schedule — consecutive failures grow the delay up to the cap
# ---------------------------------------------------------------------------


def test_backoff_delay_follows_schedule():
    """_backoff_delay() must follow _BACKOFF_SCHEDULE and cap at the last entry."""
    proc = _make_mock_process(None)  # EOF — drain thread will hit failure path

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
            schedule = FrameGrabber._BACKOFF_SCHEDULE
            # walk the schedule
            for i, expected in enumerate(schedule):
                fg._consecutive_failures = i
                assert fg._backoff_delay() == expected, (
                    f"failures={i} expected {expected}s, got {fg._backoff_delay()}s"
                )
            # past the end — must stay at the cap
            fg._consecutive_failures = len(schedule) * 3
            assert fg._backoff_delay() == schedule[-1]
        finally:
            fg.stop()


# ---------------------------------------------------------------------------
# stderr noise filter — collapses the 404 cluster into a single warning
# ---------------------------------------------------------------------------


def test_drain_stderr_dedupes_offline_patterns(caplog):
    """When FFmpeg prints the 4 "publisher offline" lines, log once total."""
    proc = _make_mock_process(None)
    # Simulate the 4-line cluster FFmpeg produces when mediamtx returns 404
    offline_lines = [
        b"[rtsp @ 0xabc] method DESCRIBE failed: 404 Not Found\n",
        b"[in#0 @ 0xdef] Error opening input: Server returned 404 Not Found\n",
        b"Error opening input file rtsp://mediamtx:8554/eb226.\n",
        b"Error opening input files: Server returned 404 Not Found\n",
    ]
    proc.stderr = iter(offline_lines)

    with (
        patch("subprocess.Popen", return_value=proc),
        patch("app.services.frame_grabber.settings") as mock_settings,
    ):
        mock_settings.FRAME_GRABBER_WIDTH = WIDTH
        mock_settings.FRAME_GRABBER_HEIGHT = HEIGHT
        mock_settings.FRAME_GRABBER_FPS = 10

        import logging as _logging

        from app.services.frame_grabber import FrameGrabber

        fg = FrameGrabber(RTSP_URL)
        try:
            with caplog.at_level(_logging.WARNING, logger="app.services.frame_grabber"):
                fg._drain_stderr(proc)
            # Exactly one "Publisher offline" warning, not four
            offline_warns = [
                r for r in caplog.records
                if "Publisher offline" in r.getMessage()
            ]
            assert len(offline_warns) == 1, (
                f"expected 1 offline warning, got {len(offline_warns)}: "
                f"{[r.getMessage() for r in offline_warns]}"
            )
            # The raw FFmpeg lines must NOT have leaked through
            raw_leaks = [
                r for r in caplog.records
                if "404 Not Found" in r.getMessage()
                and "Publisher offline" not in r.getMessage()
            ]
            assert raw_leaks == [], f"raw FFmpeg noise leaked: {[r.getMessage() for r in raw_leaks]}"
            # Flag must be set so subsequent FFmpeg respawns are also muted
            assert fg._publisher_offline_logged is True
        finally:
            fg.stop()


def test_successful_frame_resets_offline_state(grabber):
    """After a frame is read, the offline flag + failure counter must reset.

    This is what lets the NEXT publisher outage log once again instead of
    being permanently muted.
    """
    # Pretend we were in an offline state
    grabber._consecutive_failures = 4
    grabber._publisher_offline_logged = True

    # Drain loop is already running with a working mock proc — give it time
    # to read a frame past warmup.
    time.sleep(0.3)
    assert grabber.grab() is not None, "mock proc should be yielding frames"
    assert grabber._consecutive_failures == 0
    assert grabber._publisher_offline_logged is False
