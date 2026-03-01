"""Verify production-tuned config defaults."""


def test_recognition_batch_size_default():
    """Batch size must be >= 50 to handle a full classroom."""
    from app.config import settings
    assert settings.RECOGNITION_MAX_BATCH_SIZE >= 50


def test_recognition_fps_default():
    """At least 10 FPS for responsive detection metadata."""
    from app.config import settings
    assert settings.RECOGNITION_FPS >= 10.0


def test_hls_segment_duration_is_low_latency():
    """<= 1.0s segments for low-latency HLS."""
    from app.config import settings
    assert settings.HLS_SEGMENT_DURATION <= 1.0


def test_hls_playlist_window():
    """At least 3 segments in playlist for smooth playback."""
    from app.config import settings
    assert settings.HLS_PLAYLIST_SIZE >= 3
