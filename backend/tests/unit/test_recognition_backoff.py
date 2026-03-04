"""
Tests for recognition service RTSP reconnection backoff.
We verify the backoff math without touching real RTSP streams.
"""
import threading
import pytest
from unittest.mock import patch
from app.services.recognition_service import RecognitionService, RecognitionState


def make_state(room_id="test-room"):
    return RecognitionState(room_id=room_id, rtsp_url="rtsp://fake/stream")


def test_initial_backoff_is_zero():
    """State starts with no backoff."""
    state = make_state()
    assert state.reconnect_backoff == 0.0


def test_first_reconnect_sleeps_base_delay():
    """First reconnect sleeps for the base delay (2s)."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()
    state = make_state()
    state.reconnect_backoff = 0.0

    slept = []
    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep", side_effect=lambda d: slept.append(d)):
            svc._reconnect(state)

    assert any(d >= 2.0 for d in slept), f"Expected sleep >= 2s, got {slept}"


def test_reconnect_sets_backoff_after_failure():
    """After first failed reconnect, backoff is set to 2.0."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()
    state = make_state()
    state.reconnect_backoff = 0.0

    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep"):
            svc._reconnect(state)

    assert state.reconnect_backoff == 2.0, f"Expected 2.0, got {state.reconnect_backoff}"


def test_reconnect_backoff_doubles_on_second_failure():
    """Second failure doubles backoff to 4.0."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()
    state = make_state()
    state.reconnect_backoff = 2.0

    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep"):
            svc._reconnect(state)

    assert state.reconnect_backoff == 4.0, f"Expected 4.0, got {state.reconnect_backoff}"


def test_reconnect_backoff_caps_at_30():
    """Backoff does not exceed 30 seconds."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()
    state = make_state()
    state.reconnect_backoff = 16.0

    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep"):
            svc._reconnect(state)

    assert state.reconnect_backoff == 30.0, f"Expected cap at 30.0, got {state.reconnect_backoff}"


def test_successful_reconnect_resets_backoff():
    """Successful connection resets backoff to 0."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()
    state = make_state()
    state.reconnect_backoff = 8.0

    with patch.object(svc, "_open_capture", return_value=True):
        with patch("time.sleep"):
            result = svc._reconnect(state)

    assert result is True
    assert state.reconnect_backoff == 0.0, f"Expected 0.0 after success, got {state.reconnect_backoff}"
