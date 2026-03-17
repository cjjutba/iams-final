"""Tests for FFmpegPublisher write_frame deadlock prevention.

Verifies that write_frame() never hangs or raises -- it always returns
a boolean, even when FFmpeg's stdin pipe is broken or the process has died.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.pipeline.ffmpeg_publisher import FFmpegPublisher


def _make_publisher() -> FFmpegPublisher:
    return FFmpegPublisher("rtsp://fake:8554/test", 640, 480, 25)


def _dummy_frame() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestWriteFrameBrokenPipe:
    """write_frame must return False (not hang or raise) on pipe errors."""

    def test_returns_false_on_broken_pipe_error(self):
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process appears alive
        mock_proc.stdin.write.side_effect = BrokenPipeError("stdin broken")
        pub._process = mock_proc

        result = pub.write_frame(_dummy_frame())
        assert result is False

    def test_returns_false_on_os_error(self):
        """OSError (parent of BrokenPipeError) should also be caught."""
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin.write.side_effect = OSError("write failed")
        pub._process = mock_proc

        result = pub.write_frame(_dummy_frame())
        assert result is False

    def test_does_not_raise_on_broken_pipe(self):
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin.write.side_effect = BrokenPipeError
        pub._process = mock_proc

        # Must not raise
        pub.write_frame(_dummy_frame())


class TestWriteFrameDeadProcess:
    """write_frame must return False when the FFmpeg process has exited."""

    def test_returns_false_when_poll_returns_nonzero(self):
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # exited with error
        pub._process = mock_proc

        result = pub.write_frame(_dummy_frame())
        assert result is False
        # stdin.write must NOT be called when process is dead
        mock_proc.stdin.write.assert_not_called()

    def test_returns_false_when_poll_returns_zero(self):
        """Even a clean exit (code 0) means no more writing."""
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        pub._process = mock_proc

        result = pub.write_frame(_dummy_frame())
        assert result is False
        mock_proc.stdin.write.assert_not_called()

    def test_returns_false_when_process_is_none(self):
        pub = _make_publisher()
        assert pub.write_frame(_dummy_frame()) is False


class TestWriteFrameFlush:
    """write_frame must flush after writing to prevent buffering issues."""

    def test_flushes_stdin_after_write(self):
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pub._process = mock_proc

        result = pub.write_frame(_dummy_frame())
        assert result is True
        mock_proc.stdin.write.assert_called_once()
        mock_proc.stdin.flush.assert_called_once()

    def test_returns_false_on_flush_os_error(self):
        """If flush itself raises OSError, still return False."""
        pub = _make_publisher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin.flush.side_effect = OSError("flush failed")
        pub._process = mock_proc

        result = pub.write_frame(_dummy_frame())
        assert result is False
