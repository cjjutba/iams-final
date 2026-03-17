"""Tests for RTSPReader graceful exit on FFmpeg process death."""

import threading
import time
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


class TestRTSPReaderFFmpegDeath:
    """RTSPReader should exit its reader loop when FFmpeg dies."""

    def test_reader_loop_exits_on_ffmpeg_death(self):
        """When FFmpeg exits (stdout EOF + poll non-zero), reader loop exits within 5s."""
        from app.pipeline.rtsp_reader import RTSPReader

        reader = RTSPReader("rtsp://fake:8554/test", target_fps=10, width=640, height=480)

        # Build a mock process whose stdout returns empty bytes (EOF)
        # and whose poll() returns 1 (process exited with error)
        mock_proc = MagicMock()
        mock_proc.stdout.read.return_value = b""
        mock_proc.poll.return_value = 1  # process is dead

        reader._process = mock_proc
        reader._stopped = False

        # Run _reader_loop in a thread and verify it exits promptly
        loop_thread = threading.Thread(target=reader._reader_loop, daemon=True)
        loop_thread.start()
        loop_thread.join(timeout=5.0)

        assert not loop_thread.is_alive(), (
            "Reader loop did not exit within 5 seconds after FFmpeg death"
        )

    def test_reader_loop_exits_on_stdout_eof(self):
        """When stdout returns EOF mid-stream (process still looks alive), reader loop exits."""
        from app.pipeline.rtsp_reader import RTSPReader

        reader = RTSPReader("rtsp://fake:8554/test", target_fps=10, width=320, height=240)

        # Process appears alive (poll returns None), but stdout returns empty bytes
        mock_proc = MagicMock()
        mock_proc.stdout.read.return_value = b""
        mock_proc.poll.return_value = None  # process hasn't exited yet

        reader._process = mock_proc
        reader._stopped = False

        loop_thread = threading.Thread(target=reader._reader_loop, daemon=True)
        loop_thread.start()
        loop_thread.join(timeout=5.0)

        assert not loop_thread.is_alive(), (
            "Reader loop did not exit within 5 seconds after stdout EOF"
        )

    def test_read_exactly_returns_none_on_eof(self):
        """_read_exactly should return None when stdout hits EOF."""
        from app.pipeline.rtsp_reader import RTSPReader

        reader = RTSPReader("rtsp://fake:8554/test")

        mock_proc = MagicMock()
        mock_proc.stdout.read.return_value = b""
        reader._process = mock_proc

        result = reader._read_exactly(921600)
        assert result is None
