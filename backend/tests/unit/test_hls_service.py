"""
Unit tests for HLS service FFmpeg command construction.

These tests verify the FFmpeg command list that hls_service builds
without actually spawning FFmpeg. subprocess.Popen is patched so
no external process is started.
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def hls(tmp_path):
    """Return a fresh HLSService with a temp segment base dir."""
    from app.services.hls_service import HLSService
    svc = HLSService()
    # _active is a class-level dict shared across instances; clear it so each
    # test starts from a clean state and the new-stream code path is exercised.
    HLSService._active.clear()
    return svc


def _capture_cmd(hls_svc, tmp_path, room_id="room1", rtsp_url="rtsp://cam/stream"):
    """Run start_stream with mocked Popen + playlist wait; return captured cmd list."""
    captured = {}

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still alive

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return mock_proc

    # Also patch _ensure_segment_dir to avoid real filesystem writes
    fake_dir = str(tmp_path / room_id)
    import os
    os.makedirs(fake_dir, exist_ok=True)

    loop = asyncio.new_event_loop()
    try:
        with patch("subprocess.Popen", side_effect=fake_popen), \
             patch.object(hls_svc, "_ensure_segment_dir", return_value=fake_dir), \
             patch.object(hls_svc, "_wait_for_playlist", return_value=True), \
             patch("os.makedirs"):
            loop.run_until_complete(
                hls_svc.start_stream(room_id, rtsp_url, "viewer1")
            )
    finally:
        loop.close()

    return captured.get("cmd", [])


def test_ffmpeg_uses_copy_codec(hls, tmp_path):
    cmd = _capture_cmd(hls, tmp_path)
    assert "-c:v" in cmd
    idx = cmd.index("-c:v")
    assert cmd[idx + 1] == "copy", "Must remux without transcoding (zero CPU)"


def test_ffmpeg_uses_fmp4_segment_type(hls, tmp_path):
    cmd = _capture_cmd(hls, tmp_path)
    assert "-hls_segment_type" in cmd, "fMP4 segment type flag must be present"
    idx = cmd.index("-hls_segment_type")
    assert cmd[idx + 1] == "fmp4"


def test_ffmpeg_has_init_filename(hls, tmp_path):
    cmd = _capture_cmd(hls, tmp_path)
    assert "-hls_fmp4_init_filename" in cmd, "fMP4 init segment filename must be specified"
    idx = cmd.index("-hls_fmp4_init_filename")
    assert cmd[idx + 1] == "init.mp4"


def test_ffmpeg_low_latency_flags(hls, tmp_path):
    cmd = _capture_cmd(hls, tmp_path)
    fflags = None
    if "-fflags" in cmd:
        fflags = cmd[cmd.index("-fflags") + 1]
    assert fflags is not None and "nobuffer" in fflags, \
        "nobuffer fflags must be present for low-latency input"


def test_segment_duration_matches_config(hls, tmp_path):
    from app.config import settings
    cmd = _capture_cmd(hls, tmp_path)
    assert "-hls_time" in cmd
    idx = cmd.index("-hls_time")
    assert cmd[idx + 1] == str(settings.HLS_SEGMENT_DURATION), \
        f"Expected {settings.HLS_SEGMENT_DURATION}, got {cmd[idx + 1]}"


def test_playlist_size_matches_config(hls, tmp_path):
    from app.config import settings
    cmd = _capture_cmd(hls, tmp_path)
    assert "-hls_list_size" in cmd
    idx = cmd.index("-hls_list_size")
    assert cmd[idx + 1] == str(settings.HLS_PLAYLIST_SIZE)


def test_segment_filename_uses_m4s_extension(hls, tmp_path):
    cmd = _capture_cmd(hls, tmp_path)
    assert "-hls_segment_filename" in cmd
    idx = cmd.index("-hls_segment_filename")
    seg_pattern = cmd[idx + 1]
    assert seg_pattern.endswith(".m4s"), \
        f"fMP4 segments must use .m4s extension, got: {seg_pattern}"
