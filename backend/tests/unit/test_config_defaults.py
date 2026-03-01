"""Verify production-tuned config defaults."""


def test_recognition_batch_size_default():
    """Production default is exactly 50 — handles a full classroom of students."""
    from app.config import settings
    assert settings.RECOGNITION_MAX_BATCH_SIZE == 50


def test_recognition_fps_default():
    """
    Recognition FPS should be low (2–5) to avoid log spam and CPU pressure.

    10 FPS generated a downscale debug log every 100ms which drowned out
    meaningful events.  2 FPS is sufficient for continuous presence tracking.
    """
    from app.config import settings
    assert 1.0 <= settings.RECOGNITION_FPS <= 5.0


def test_hls_segment_duration_is_low_latency():
    """<= 1.0s segments for low-latency HLS."""
    from app.config import settings
    assert settings.HLS_SEGMENT_DURATION <= 1.0


def test_hls_playlist_window():
    """At least 3 segments in playlist for smooth playback."""
    from app.config import settings
    assert settings.HLS_PLAYLIST_SIZE >= 3


def test_mediamtx_bin_path_default():
    from app.config import settings
    assert settings.MEDIAMTX_BIN_PATH == "bin/mediamtx"


def test_mediamtx_config_path_default():
    from app.config import settings
    assert settings.MEDIAMTX_CONFIG_PATH == "mediamtx.yml"
