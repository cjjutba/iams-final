"""Tests for WebRTC configuration defaults."""
from app.config import Settings


def test_use_webrtc_streaming_default():
    """WebRTC streaming is enabled by default."""
    s = Settings()
    assert s.USE_WEBRTC_STREAMING is True


def test_mediamtx_api_url_default():
    """mediamtx REST API points to localhost:9997 by default."""
    s = Settings()
    assert s.MEDIAMTX_API_URL == "http://localhost:9997"


def test_mediamtx_webrtc_url_default():
    """mediamtx WHEP endpoint points to localhost:8889 by default."""
    s = Settings()
    assert s.MEDIAMTX_WEBRTC_URL == "http://localhost:8889"


def test_webrtc_stun_urls_default():
    """Google public STUN server is configured by default."""
    s = Settings()
    assert "stun:stun.l.google.com:19302" in s.WEBRTC_STUN_URLS


def test_webrtc_turn_url_default_empty():
    """TURN URL is empty by default (LAN deployment doesn't need it)."""
    s = Settings()
    assert s.WEBRTC_TURN_URL == ""


def test_webrtc_turn_credentials_default_empty():
    """TURN credentials are empty by default."""
    s = Settings()
    assert s.WEBRTC_TURN_USERNAME == ""
    assert s.WEBRTC_TURN_CREDENTIAL == ""
