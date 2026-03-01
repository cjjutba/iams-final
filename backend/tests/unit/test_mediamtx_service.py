"""
Unit tests for MediamtxService.

mediamtx is an external binary (not part of the test suite), so all
subprocess and HTTP calls are mocked.
"""
import asyncio
import signal
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def svc():
    """Fresh MediamtxService with cleared state."""
    from app.services.mediamtx_service import MediamtxService
    s = MediamtxService()
    s._process = None
    return s


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------

def test_start_launches_process_with_correct_args(svc, tmp_path):
    """start() must invoke Popen with [bin_path, config_path]."""
    fake_bin = tmp_path / "mediamtx"
    fake_bin.touch()
    fake_cfg = tmp_path / "mediamtx.yml"
    fake_cfg.touch()

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # alive

    loop = asyncio.new_event_loop()
    try:
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch(
                 "app.services.mediamtx_service.MediamtxService._wait_for_api",
                 new_callable=AsyncMock,
                 return_value=True,
             ):
            result = loop.run_until_complete(
                svc.start(bin_path=str(fake_bin), config_path=str(fake_cfg))
            )
    finally:
        loop.close()

    assert result is True
    mock_popen.assert_called_once()
    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == str(fake_bin)
    assert cmd[1] == str(fake_cfg)


def test_start_returns_false_when_binary_missing(svc, tmp_path):
    """start() must return False (not raise) when the binary does not exist."""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            svc.start(
                bin_path=str(tmp_path / "nonexistent"),
                config_path=str(tmp_path / "mediamtx.yml"),
            )
        )
    finally:
        loop.close()

    assert result is False
    assert svc._process is None


def test_start_returns_false_when_process_exits_immediately(svc, tmp_path):
    """start() must return False when mediamtx exits right after launch."""
    fake_bin = tmp_path / "mediamtx"
    fake_bin.touch()

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1       # exited with code 1
    mock_proc.returncode = 1

    loop = asyncio.new_event_loop()
    try:
        with patch("subprocess.Popen", return_value=mock_proc), \
             patch(
                 "app.services.mediamtx_service.MediamtxService._wait_for_api",
                 new_callable=AsyncMock,
                 return_value=True,
             ):
            result = loop.run_until_complete(
                svc.start(bin_path=str(fake_bin), config_path=str(fake_bin))
            )
    finally:
        loop.close()

    assert result is False


def test_start_returns_false_when_api_does_not_come_up(svc, tmp_path):
    """start() must return False when mediamtx starts but API is unreachable."""
    fake_bin = tmp_path / "mediamtx"
    fake_bin.touch()

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process alive but API never responds

    loop = asyncio.new_event_loop()
    try:
        with patch("subprocess.Popen", return_value=mock_proc), \
             patch(
                 "app.services.mediamtx_service.MediamtxService._wait_for_api",
                 new_callable=AsyncMock,
                 return_value=False,   # timeout
             ):
            result = loop.run_until_complete(
                svc.start(bin_path=str(fake_bin), config_path=str(fake_bin))
            )
    finally:
        loop.close()

    assert result is False


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

def test_stop_sends_sigterm_and_waits(svc):
    """stop() must send SIGTERM to the process and wait for it."""
    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0
    svc._process = mock_proc

    svc.stop()

    mock_proc.send_signal.assert_called_once_with(signal.SIGTERM)
    mock_proc.wait.assert_called()
    assert svc._process is None


def test_stop_does_nothing_when_not_started(svc):
    """stop() must be a no-op when mediamtx was never started."""
    svc.stop()  # should not raise


# ---------------------------------------------------------------------------
# is_healthy()
# ---------------------------------------------------------------------------

def test_is_healthy_returns_false_when_not_started(svc):
    assert svc.is_healthy() is False


def test_is_healthy_returns_true_when_process_alive(svc):
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # alive
    svc._process = mock_proc
    assert svc.is_healthy() is True


def test_is_healthy_returns_false_when_process_dead(svc):
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # exited
    svc._process = mock_proc
    assert svc.is_healthy() is False
