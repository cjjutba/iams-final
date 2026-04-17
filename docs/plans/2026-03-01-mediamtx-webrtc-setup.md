# mediamtx WebRTC Setup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Start mediamtx automatically when FastAPI starts so WebRTC streaming works with ~200ms latency instead of HLS's ~1s.

**Architecture:** A new `MediamtxService` class manages the mediamtx binary as a subprocess (started/stopped in FastAPI's startup/shutdown events). The mobile WebRTC code and FastAPI WebRTC router are already complete — mediamtx just isn't running. The existing HLS fallback stays intact.

**Tech Stack:** mediamtx v1.x (single binary, macOS arm64), subprocess.Popen, httpx for health-polling, pytest+unittest.mock for tests.

---

## Context

The codebase already has:
- `backend/app/services/webrtc_service.py` — proxies WHEP offers to mediamtx
- `backend/app/routers/webrtc.py` — `/api/v1/webrtc/{schedule_id}/offer` endpoint
- `mobile/src/hooks/useWebRTC.ts` — full RTCPeerConnection handshake
- `backend/app/config.py` — `MEDIAMTX_API_URL`, `MEDIAMTX_WEBRTC_URL`, `USE_WEBRTC_STREAMING`
- `backend/app/main.py` — uses `@app.on_event("startup")` / `@app.on_event("shutdown")` pattern

**What is missing:** The mediamtx binary and a service to launch it.

**Key files to understand before starting:**
- `backend/app/services/hls_service.py` — reference for subprocess management pattern
- `backend/app/config.py` lines 80–88 — existing WebRTC config fields
- `backend/app/main.py` lines 83–259 — startup/shutdown event structure

---

## Task 1: Download Script + .gitignore

**Files:**
- Create: `backend/scripts/download_mediamtx.sh`
- Modify: `.gitignore` (root)

**Step 1: Add mediamtx binary to .gitignore**

Open `.gitignore` at the repo root. Add these lines at the bottom:

```gitignore
# mediamtx binary (downloaded locally, not committed)
backend/bin/mediamtx
backend/bin/mediamtx.exe
```

**Step 2: Create the download script**

Create `backend/scripts/download_mediamtx.sh`:

```bash
#!/usr/bin/env bash
# Downloads the mediamtx binary for the current platform into backend/bin/
# Usage: bash backend/scripts/download_mediamtx.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"
BINARY="$BIN_DIR/mediamtx"

if [[ -f "$BINARY" ]]; then
  echo "mediamtx already exists at $BINARY"
  exit 0
fi

# Fetch latest release tag from GitHub API
echo "Fetching latest mediamtx release..."
VERSION=$(curl -s https://api.github.com/repos/bluenviron/mediamtx/releases/latest \
  | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": "\(.*\)".*/\1/')

if [[ -z "$VERSION" ]]; then
  echo "ERROR: Could not determine latest mediamtx version" >&2
  exit 1
fi

echo "Latest version: $VERSION"

# Determine OS/arch
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS" in
  darwin)  PLATFORM="darwin" ;;
  linux)   PLATFORM="linux"  ;;
  *)       echo "ERROR: Unsupported OS: $OS" >&2; exit 1 ;;
esac

case "$ARCH" in
  arm64|aarch64) GOARCH="arm64" ;;
  x86_64)        GOARCH="amd64" ;;
  *)             echo "ERROR: Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

FILENAME="mediamtx_${VERSION}_${PLATFORM}_${GOARCH}.tar.gz"
URL="https://github.com/bluenviron/mediamtx/releases/download/${VERSION}/${FILENAME}"

echo "Downloading $URL ..."
mkdir -p "$BIN_DIR"
TMP=$(mktemp -d)
curl -L -o "$TMP/$FILENAME" "$URL"
tar -xzf "$TMP/$FILENAME" -C "$TMP"
mv "$TMP/mediamtx" "$BINARY"
chmod +x "$BINARY"
rm -rf "$TMP"

echo "mediamtx installed at $BINARY"
echo "Version: $($BINARY --version 2>&1 | head -1)"
```

**Step 3: Make it executable**

```bash
chmod +x backend/scripts/download_mediamtx.sh
```

**Step 4: Run it to verify it works**

```bash
cd /path/to/iams
bash backend/scripts/download_mediamtx.sh
```

Expected: binary downloaded to `backend/bin/mediamtx`, version printed.

```bash
ls -lh backend/bin/mediamtx
```

Expected: file exists, size ~30–60 MB.

**Step 5: Commit**

```bash
git add .gitignore backend/scripts/download_mediamtx.sh
git commit -m "feat: add mediamtx download script for macOS arm64"
```

---

## Task 2: mediamtx.yml Config

**Files:**
- Create: `backend/mediamtx.yml`

**Step 1: Create the config**

Create `backend/mediamtx.yml`:

```yaml
# mediamtx configuration for IAMS
# mediamtx bridges RTSP camera streams to WebRTC (WHEP) for mobile playback.
# Paths are created dynamically at runtime via the REST API by webrtc_service.py.

logLevel: warn        # suppress routine logs; FastAPI has its own logging

# REST API — used by FastAPI's webrtc_service to create/delete paths
api: yes
apiAddress: :9997

# RTSP — mediamtx pulls from camera on demand when a viewer connects
rtsp: yes
rtspAddress: :8554
rtspsAddress: :8322

# WebRTC (WHEP) — mobile clients negotiate here via FastAPI proxy
webrtc: yes
webrtcAddress: :8889

# No HLS or other protocols needed
hls: no
srt: no
rtmp: no

# All paths are added dynamically via the API (sourceOnDemand=true)
# FastAPI calls POST /v3/config/paths/add/{room_id} for each active room.
paths: {}
```

**Step 2: Verify mediamtx accepts this config**

```bash
cd backend
./bin/mediamtx mediamtx.yml &
sleep 2
curl -s http://localhost:9997/v3/config/global | python3 -m json.tool | head -20
kill %1
```

Expected: JSON response from mediamtx API (no errors).

**Step 3: Commit**

```bash
git add backend/mediamtx.yml
git commit -m "feat: add mediamtx.yml config (WebRTC + API, no HLS/RTMP)"
```

---

## Task 3: Config Settings

**Files:**
- Modify: `backend/app/config.py` (add 2 settings)
- Modify: `backend/tests/unit/test_config_defaults.py` (add 2 tests)

**Step 1: Write the failing tests first**

Open `backend/tests/unit/test_config_defaults.py` and add at the bottom:

```python
def test_mediamtx_bin_path_default():
    """Binary path must point into the bin/ directory."""
    from app.config import settings
    assert "mediamtx" in settings.MEDIAMTX_BIN_PATH.lower()


def test_mediamtx_config_path_default():
    """Config path must be a .yml file."""
    from app.config import settings
    assert settings.MEDIAMTX_CONFIG_PATH.endswith(".yml")
```

**Step 2: Run to confirm they fail**

```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_config_defaults.py::test_mediamtx_bin_path_default \
       tests/unit/test_config_defaults.py::test_mediamtx_config_path_default -v
```

Expected: `FAILED` — `AttributeError: 'Settings' object has no attribute 'MEDIAMTX_BIN_PATH'`

**Step 3: Add the settings**

Open `backend/app/config.py`. Find the WebRTC block (around line 80):

```python
    # WebRTC Streaming (mediamtx + WHEP — replaces HLS for <300ms latency)
    USE_WEBRTC_STREAMING: bool = True
    MEDIAMTX_API_URL: str = "http://localhost:9997"
    MEDIAMTX_WEBRTC_URL: str = "http://localhost:8889"
    WEBRTC_STUN_URLS: str = "stun:stun.l.google.com:19302"
    WEBRTC_TURN_URL: str = ""
    WEBRTC_TURN_USERNAME: str = ""
    WEBRTC_TURN_CREDENTIAL: str = ""
```

Add two lines immediately after `WEBRTC_TURN_CREDENTIAL`:

```python
    MEDIAMTX_BIN_PATH: str = "bin/mediamtx"      # Path to mediamtx binary (relative to backend/)
    MEDIAMTX_CONFIG_PATH: str = "mediamtx.yml"    # Path to mediamtx config (relative to backend/)
```

**Step 4: Run to confirm they pass**

```bash
pytest tests/unit/test_config_defaults.py::test_mediamtx_bin_path_default \
       tests/unit/test_config_defaults.py::test_mediamtx_config_path_default -v
```

Expected: `2 passed`

**Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/unit/test_config_defaults.py
git commit -m "feat: add MEDIAMTX_BIN_PATH and MEDIAMTX_CONFIG_PATH config settings"
```

---

## Task 4: MediamtxService (core implementation)

**Files:**
- Create: `backend/tests/unit/test_mediamtx_service.py`
- Create: `backend/app/services/mediamtx_service.py`

**Step 1: Write all tests first**

Create `backend/tests/unit/test_mediamtx_service.py`:

```python
"""
Unit tests for MediamtxService.

mediamtx is an external binary (not part of the test suite), so all
subprocess and HTTP calls are mocked.  Tests mirror the pattern used
in test_hls_service.py.
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
```

**Step 2: Run to confirm all fail**

```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_mediamtx_service.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'app.services.mediamtx_service'`

**Step 3: Implement MediamtxService**

Create `backend/app/services/mediamtx_service.py`:

```python
"""
MediamtxService

Manages the mediamtx binary as a subprocess alongside the FastAPI process.
mediamtx bridges RTSP camera streams to WebRTC (WHEP protocol) for
sub-300ms mobile playback.

Key design decisions:
- start() is async so it can poll the mediamtx REST API with asyncio.sleep
  without blocking the FastAPI event loop during startup
- On failure, start() returns False and logs a clear error; FastAPI still
  starts and falls back to HLS automatically (existing behaviour)
- stop() is synchronous (called from shutdown_event which allows sync calls)
"""

import asyncio
import os
import signal
import subprocess
from typing import Optional

import httpx

from app.config import settings, logger


class MediamtxService:
    """Lifecycle manager for the mediamtx subprocess."""

    _process: Optional[subprocess.Popen] = None

    async def start(
        self,
        bin_path: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> bool:
        """
        Launch mediamtx and wait for its REST API to become ready.

        Args:
            bin_path:    Override binary path (used in tests).
            config_path: Override config path (used in tests).

        Returns:
            True if mediamtx is running and API is ready, False otherwise.
            FastAPI startup continues regardless of the return value.
        """
        # Resolve paths relative to the backend/ directory.
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_bin = os.path.abspath(bin_path or os.path.join(base, settings.MEDIAMTX_BIN_PATH))
        resolved_cfg = os.path.abspath(config_path or os.path.join(base, settings.MEDIAMTX_CONFIG_PATH))

        if not os.path.isfile(resolved_bin):
            logger.error(
                f"mediamtx binary not found at {resolved_bin}. "
                "Run: bash backend/scripts/download_mediamtx.sh"
            )
            return False

        logger.info(f"Starting mediamtx: {resolved_bin} {resolved_cfg}")

        try:
            self._process = subprocess.Popen(
                [resolved_bin, resolved_cfg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.error(f"Failed to start mediamtx: {exc}")
            return False

        # Wait for the mediamtx REST API to become ready (max 5 s).
        api_ready = await self._wait_for_api(timeout=5.0)

        # If the process exited immediately, it was a bad config or port conflict.
        if self._process.poll() is not None:
            logger.error(
                f"mediamtx exited immediately (rc={self._process.returncode}). "
                "Check mediamtx.yml and that ports 9997/8889/8554 are free."
            )
            self._process = None
            return False

        if not api_ready:
            logger.error(
                "mediamtx started but REST API did not respond within 5 s. "
                "Falling back to HLS streaming."
            )
            self.stop()
            return False

        logger.info("mediamtx is ready (WebRTC streaming active)")
        return True

    def stop(self) -> None:
        """Terminate the mediamtx process (SIGTERM → wait 5 s → SIGKILL)."""
        proc = self._process
        if proc is None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        except Exception as exc:
            logger.warning(f"Error stopping mediamtx: {exc}")
        finally:
            self._process = None
        logger.info("mediamtx stopped")

    def is_healthy(self) -> bool:
        """Return True if the mediamtx process is still running."""
        return self._process is not None and self._process.poll() is None

    async def _wait_for_api(self, timeout: float = 5.0) -> bool:
        """Poll GET /v3/config/global until mediamtx responds or timeout."""
        url = f"{settings.MEDIAMTX_API_URL}/v3/config/global"
        elapsed = 0.0
        interval = 0.25
        while elapsed < timeout:
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(interval)
            elapsed += interval
        return False


# Module-level singleton — imported by main.py
mediamtx_service = MediamtxService()
```

**Step 4: Run tests to confirm all pass**

```bash
pytest tests/unit/test_mediamtx_service.py -v
```

Expected: `9 passed`

**Step 5: Commit**

```bash
git add backend/app/services/mediamtx_service.py \
        backend/tests/unit/test_mediamtx_service.py
git commit -m "feat: add MediamtxService subprocess manager with tests"
```

---

## Task 5: Wire MediamtxService into main.py

**Files:**
- Modify: `backend/app/main.py`

No new tests needed — the service is already fully tested. This task is wiring only.

**Step 1: Add mediamtx start to startup_event**

Open `backend/app/main.py`. Find the block near line 211:

```python
    # Create HLS segment directory (if HLS streaming enabled)
    if settings.USE_HLS_STREAMING:
        import os
        os.makedirs(settings.HLS_SEGMENT_DIR, exist_ok=True)
        logger.info(f"HLS streaming enabled (segment dir: {settings.HLS_SEGMENT_DIR})")

    logger.info(f"{settings.APP_NAME} startup complete")
```

Insert the mediamtx startup block **before** the HLS block:

```python
    # Start mediamtx (WebRTC bridge: RTSP → WHEP)
    if settings.USE_WEBRTC_STREAMING:
        try:
            from app.services.mediamtx_service import mediamtx_service
            started = await mediamtx_service.start()
            if started:
                logger.info("WebRTC streaming ready (mediamtx running)")
            else:
                logger.warning(
                    "mediamtx failed to start — WebRTC unavailable, falling back to HLS"
                )
        except Exception as e:
            logger.error(f"Failed to start mediamtx: {e}")

    # Create HLS segment directory (if HLS streaming enabled)
    if settings.USE_HLS_STREAMING:
```

**Step 2: Add mediamtx stop to shutdown_event**

Find the shutdown block near line 240:

```python
    # Stop HLS and recognition services
    if settings.USE_HLS_STREAMING:
        try:
            from app.services.hls_service import hls_service
            from app.services.recognition_service import recognition_service
            logger.info("Stopping HLS and recognition services...")
            await hls_service.cleanup_all()
            await recognition_service.cleanup_all()
        except Exception as e:
            logger.error(f"Failed to stop HLS/recognition services: {e}")
```

Add the mediamtx stop block **immediately after** (after the HLS block):

```python
    # Stop mediamtx
    if settings.USE_WEBRTC_STREAMING:
        try:
            from app.services.mediamtx_service import mediamtx_service
            logger.info("Stopping mediamtx...")
            mediamtx_service.stop()
        except Exception as e:
            logger.error(f"Failed to stop mediamtx: {e}")
```

**Step 3: Run the full test suite to confirm nothing regressed**

```bash
cd backend && source venv/bin/activate
pytest -v 2>&1 | tail -10
```

Expected: all existing tests pass, new mediamtx tests pass. Zero failures.

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: start/stop mediamtx in FastAPI startup/shutdown events"
```

---

## Task 6: Download Binary and Smoke Test

This task is a runtime verification — no code changes.

**Step 1: Download the mediamtx binary**

```bash
cd /path/to/iams
bash backend/scripts/download_mediamtx.sh
```

Expected output:
```
Fetching latest mediamtx release...
Latest version: vX.Y.Z
Downloading ...
mediamtx installed at backend/bin/mediamtx
Version: mediamtx vX.Y.Z ...
```

**Step 2: Start the FastAPI server**

```bash
cd backend && source venv/bin/activate
python run.py
```

Look for these log lines in the first few seconds:
```
INFO  - iams - Starting mediamtx: .../bin/mediamtx .../mediamtx.yml
INFO  - iams - mediamtx is ready (WebRTC streaming active)
INFO  - iams - WebRTC streaming ready (mediamtx running)
```

**Step 3: Verify mediamtx API is accessible**

In a second terminal:
```bash
curl -s http://localhost:9997/v3/config/global | python3 -m json.tool | head -5
```

Expected: JSON response (logLevel, api, rtsp, webrtc fields).

**Step 4: Open the faculty live feed in the mobile app**

In the mobile app logs, look for:
```
Live stream WS connected: ... mode=webrtc
```

Instead of the previous:
```
WebRTC: cannot reach mediamtx ... falling back to HLS
```

**Step 5: Stop the server (Ctrl+C)**

Look for:
```
INFO  - iams - Stopping mediamtx...
INFO  - iams - mediamtx stopped
```

Verify no orphaned mediamtx process:
```bash
pgrep mediamtx || echo "no orphaned process"
```

Expected: `no orphaned process`

---

## Definition of Done

- [ ] `backend/scripts/download_mediamtx.sh` downloads correct binary for current platform
- [ ] `backend/mediamtx.yml` accepted by mediamtx without errors
- [ ] `MEDIAMTX_BIN_PATH` and `MEDIAMTX_CONFIG_PATH` in Settings
- [ ] `MediamtxService.start()` returns True when binary exists and API comes up
- [ ] `MediamtxService.stop()` sends SIGTERM and cleans up
- [ ] 9 unit tests in `test_mediamtx_service.py` pass
- [ ] Full pytest suite still passes (no regressions)
- [ ] `python run.py` log shows "WebRTC streaming ready"
- [ ] Mobile app logs show `mode=webrtc` instead of HLS fallback
