"""Verify production-tuned config defaults."""


def test_recognition_batch_size_default():
    """Production default is exactly 50 — handles a full classroom of students."""
    from app.config import settings
    assert settings.RECOGNITION_MAX_BATCH_SIZE == 50


def test_recognition_fps_default():
    """
    Recognition FPS should be reasonable for real-time detection overlay.

    15 FPS balances smooth bounding-box updates with CPU pressure.
    """
    from app.config import settings
    assert 1.0 <= settings.RECOGNITION_FPS <= 30.0


def test_mediamtx_bin_path_default():
    from app.config import settings
    assert settings.MEDIAMTX_BIN_PATH == "bin/mediamtx"


def test_mediamtx_config_path_default():
    from app.config import settings
    assert settings.MEDIAMTX_CONFIG_PATH == "mediamtx.yml"


def test_insightface_defaults():
    from app.config import Settings
    s = Settings()
    assert s.INSIGHTFACE_MODEL == "buffalo_l"
    assert s.INSIGHTFACE_DET_SIZE == 480
