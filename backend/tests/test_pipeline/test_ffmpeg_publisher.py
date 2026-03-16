"""Tests for FFmpegPublisher -- encodes frames and pushes RTSP."""

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

    def test_write_frame_returns_false_when_process_dead(self):
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        pub = FFmpegPublisher("rtsp://fake:8554/test", 640, 480, 25)
        # No process started
        assert pub._process is None

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert pub.write_frame(frame) is False

    def test_stop_terminates_process(self):
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        pub = FFmpegPublisher("rtsp://fake:8554/test", 640, 480, 25)
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        pub._process = mock_proc

        pub.stop()
        mock_proc.stdin.close.assert_called_once()
        mock_proc.terminate.assert_called_once()
        assert pub._process is None

    def test_is_alive_property(self):
        from app.pipeline.ffmpeg_publisher import FFmpegPublisher

        pub = FFmpegPublisher("rtsp://fake:8554/test", 640, 480, 25)
        assert pub.is_alive is False

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Still running
        pub._process = mock_proc
        assert pub.is_alive is True

        mock_proc.poll.return_value = 1  # Exited
        assert pub.is_alive is False
