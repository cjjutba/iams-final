# Edge-to-Cloud WebRTC Live Streaming — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable real-time live camera feed in the mobile app when the backend runs on a cloud VPS, by having the RPi push the camera's RTSP stream to the VPS via FFmpeg, where mediamtx serves it to the mobile app via WebRTC.

**Architecture:** RPi spawns FFmpeg to relay the camera's RTSP sub-stream to the VPS mediamtx container (`-c copy`, no transcoding). mediamtx runs as a Docker sidecar on the VPS, receiving the RTSP push and serving WebRTC (WHEP) to the mobile app. The backend's existing WebRTC signaling proxy (`webrtc.py`, `webrtc_service.py`) handles SDP negotiation. Detection metadata continues over the existing WebSocket.

**Tech Stack:** FFmpeg (edge), mediamtx (Docker on VPS), FastAPI (backend), react-native-webrtc (mobile, already implemented)

**Design doc:** `docs/plans/2026-03-12-edge-to-cloud-webrtc-streaming-design.md`

---

## Task 1: Add Stream Relay Config to Edge Device

**Files:**
- Modify: `edge/app/config.py:36-93`
- Modify: `edge/.env.example`

**Step 1: Add stream relay settings to Config class**

In `edge/app/config.py`, add these fields inside `class Config` after the Session Awareness block (after line 85):

```python
    # ===== Stream Relay Configuration =====
    # When enabled, FFmpeg relays the camera RTSP stream to the VPS mediamtx
    # so faculty can view live video from any network via WebRTC.
    STREAM_RELAY_ENABLED: bool = os.getenv("STREAM_RELAY_ENABLED", "false").lower() in ("true", "1", "yes")
    STREAM_RELAY_URL: str = os.getenv("STREAM_RELAY_URL", "")  # e.g., rtsp://167.71.217.44:8554
    STREAM_RELAY_RETRY_DELAY: int = int(os.getenv("STREAM_RELAY_RETRY_DELAY", "5"))
```

Add validation in `validate()` after the session poll interval check (after line 162):

```python
        # Stream relay validation
        if cls.STREAM_RELAY_ENABLED and not cls.STREAM_RELAY_URL:
            errors.append("STREAM_RELAY_URL is required when STREAM_RELAY_ENABLED=true")

        if cls.STREAM_RELAY_URL and not cls.STREAM_RELAY_URL.startswith("rtsp://"):
            errors.append(f"STREAM_RELAY_URL must start with rtsp:// (got: {cls.STREAM_RELAY_URL[:30]}...)")
```

**Step 2: Add env vars to .env.example**

Append to `edge/.env.example` before the Logging section:

```bash
# ===== Stream Relay Configuration =====
# When enabled, FFmpeg relays the camera RTSP sub-stream to the VPS mediamtx
# for WebRTC live viewing by faculty from any network.
# Requires FFmpeg installed: sudo apt install ffmpeg
STREAM_RELAY_ENABLED=false

# VPS mediamtx RTSP ingest URL (no trailing slash, no path)
# The room ID is appended automatically: rtsp://VPS_IP:8554/room-{room_id}
# Example: STREAM_RELAY_URL=rtsp://167.71.217.44:8554
STREAM_RELAY_URL=

# Seconds to wait before retrying FFmpeg after it dies
STREAM_RELAY_RETRY_DELAY=5
```

**Step 3: Commit**

```bash
git add edge/app/config.py edge/.env.example
git commit -m "feat(edge): add stream relay config for FFmpeg RTSP push to VPS"
```

---

## Task 2: Create Edge Stream Relay Module

**Files:**
- Create: `edge/app/stream_relay.py`

**Step 1: Create stream_relay.py**

```python
"""
Stream Relay — FFmpeg RTSP Push to VPS

Manages an FFmpeg subprocess that relays the camera's RTSP sub-stream
to the VPS mediamtx instance. mediamtx then serves the stream to the
mobile app via WebRTC (WHEP protocol).

Key design decisions:
- Uses -c copy (no transcoding) → ~2-3% CPU on RPi, ~500 Kbps upload
- Session-aware: starts when a session becomes active, stops when it ends
- Auto-reconnects if FFmpeg dies (configurable retry delay)
- Runs in a background thread so it doesn't block the scan loop
"""

import subprocess
import shutil
import threading
import time
from typing import Optional

from app.config import config, logger


class StreamRelay:
    """Manages FFmpeg subprocess for RTSP relay to VPS mediamtx."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_room_id: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """True if the relay thread is active and FFmpeg is alive."""
        return (
            self._process is not None
            and self._process.poll() is None
        )

    def start(self, room_id: str) -> bool:
        """
        Start relaying the camera RTSP stream to VPS mediamtx.

        Spawns a background thread that keeps FFmpeg running and
        auto-restarts it on failure.

        Args:
            room_id: Room identifier (used as mediamtx path name).

        Returns:
            True if relay was started, False if disabled or misconfigured.
        """
        if not config.STREAM_RELAY_ENABLED:
            logger.debug("Stream relay is disabled")
            return False

        if not config.RTSP_URL:
            logger.warning("Stream relay enabled but no RTSP_URL configured")
            return False

        if not config.STREAM_RELAY_URL:
            logger.warning("Stream relay enabled but no STREAM_RELAY_URL configured")
            return False

        if not shutil.which("ffmpeg"):
            logger.error("Stream relay: ffmpeg not found in PATH")
            return False

        # Stop any existing relay first
        if self._thread and self._thread.is_alive():
            self.stop()

        self._current_room_id = room_id
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="stream-relay",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            f"Stream relay started: {config.RTSP_URL} → "
            f"{config.STREAM_RELAY_URL}/room-{room_id}"
        )
        return True

    def stop(self) -> None:
        """Stop the relay. Kills FFmpeg and joins the background thread."""
        self._stop_event.set()
        self._kill_ffmpeg()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        self._thread = None
        self._current_room_id = None
        logger.info("Stream relay stopped")

    def _run_loop(self) -> None:
        """
        Background thread: keep FFmpeg running until stop() is called.

        On FFmpeg exit (crash, network error), waits STREAM_RELAY_RETRY_DELAY
        seconds then restarts. This provides automatic recovery from transient
        network failures between the RPi and VPS.
        """
        while not self._stop_event.is_set():
            try:
                self._start_ffmpeg()
            except Exception as e:
                logger.error(f"Stream relay: failed to start FFmpeg: {e}")

            # Wait for FFmpeg to exit or stop signal
            while not self._stop_event.is_set():
                if self._process is None:
                    break
                ret = self._process.poll()
                if ret is not None:
                    logger.warning(f"Stream relay: FFmpeg exited (code={ret})")
                    self._process = None
                    break
                time.sleep(1)

            # If not stopped, wait before retrying
            if not self._stop_event.is_set():
                delay = config.STREAM_RELAY_RETRY_DELAY
                logger.info(f"Stream relay: restarting FFmpeg in {delay}s...")
                self._stop_event.wait(delay)

    def _start_ffmpeg(self) -> None:
        """Launch FFmpeg subprocess to push RTSP stream to VPS."""
        dest = f"{config.STREAM_RELAY_URL}/room-{self._current_room_id}"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-rtsp_transport", config.RTSP_TRANSPORT,
            "-i", config.RTSP_URL,
            "-c", "copy",
            "-f", "rtsp",
            dest,
        ]

        logger.info(f"Stream relay: launching FFmpeg → {dest}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def _kill_ffmpeg(self) -> None:
        """Terminate the FFmpeg process if running."""
        proc = self._process
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        except Exception as e:
            logger.warning(f"Stream relay: error killing FFmpeg: {e}")
        finally:
            self._process = None


# Module-level singleton
stream_relay = StreamRelay()
```

**Step 2: Commit**

```bash
git add edge/app/stream_relay.py
git commit -m "feat(edge): add stream_relay module for FFmpeg RTSP push to VPS"
```

---

## Task 3: Integrate Stream Relay into Edge Main Loop

**Files:**
- Modify: `edge/app/main.py:27-28` (imports)
- Modify: `edge/app/main.py:42-49` (EdgeDevice.__init__)
- Modify: `edge/app/main.py:107-131` (shutdown)
- Modify: `edge/app/main.py:158-168` (_check_session, session transition handling)

**Step 1: Add import**

After the existing imports at line 32, add:

```python
from app.stream_relay import stream_relay
```

**Step 2: Add relay state to __init__**

In `EdgeDevice.__init__`, after `self.session_poll_interval = config.SESSION_POLL_INTERVAL` (line 65), add:

```python
        # Stream relay
        self.stream_relay_enabled = config.STREAM_RELAY_ENABLED
```

**Step 3: Start/stop relay on session transitions**

In `_check_session()`, after the log transitions block (after line 166), add relay start/stop logic:

```python
        # Start/stop stream relay on session transitions
        if self.stream_relay_enabled:
            if active and not prev_active:
                stream_relay.start(self.room_id)
            elif not active and prev_active:
                stream_relay.stop()
```

**Step 4: Stop relay in shutdown()**

In `shutdown()`, after `self.is_running = False` (line 113), before stopping the retry worker, add:

```python
        # Stop stream relay
        if self.stream_relay_enabled:
            stream_relay.stop()
```

**Step 5: Run edge device locally to verify no import errors**

```bash
cd edge
python -c "from app.stream_relay import stream_relay; print('OK')"
```

Expected: `OK`

**Step 6: Commit**

```bash
git add edge/app/main.py
git commit -m "feat(edge): integrate stream relay into session lifecycle"
```

---

## Task 4: Add MEDIAMTX_EXTERNAL Setting to Backend

**Files:**
- Modify: `backend/app/config.py:104-115`

**Step 1: Add MEDIAMTX_EXTERNAL setting**

In `backend/app/config.py`, after `USE_WEBRTC_STREAMING` (line 105), add:

```python
    MEDIAMTX_EXTERNAL: bool = False                         # True = mediamtx runs as separate container (skip subprocess)
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(backend): add MEDIAMTX_EXTERNAL config for containerized mediamtx"
```

---

## Task 5: Support External mediamtx in MediamtxService

**Files:**
- Modify: `backend/app/services/mediamtx_service.py:33-96`
- Modify: `backend/tests/unit/test_mediamtx_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/unit/test_mediamtx_service.py`:

```python
def test_start_external_skips_subprocess_and_checks_api(svc):
    """When MEDIAMTX_EXTERNAL=True, start() must NOT launch a subprocess
    but still verify the API is reachable."""
    loop = asyncio.new_event_loop()
    try:
        with patch("app.services.mediamtx_service.settings") as mock_settings, \
             patch("subprocess.Popen") as mock_popen, \
             patch(
                 "app.services.mediamtx_service.MediamtxService._wait_for_api",
                 new_callable=AsyncMock,
                 return_value=True,
             ):
            mock_settings.MEDIAMTX_EXTERNAL = True
            mock_settings.MEDIAMTX_API_URL = "http://mediamtx:9997"
            result = loop.run_until_complete(svc.start())
    finally:
        loop.close()

    assert result is True
    mock_popen.assert_not_called()


def test_start_external_returns_false_when_api_unreachable(svc):
    """When MEDIAMTX_EXTERNAL=True and the API is unreachable, return False."""
    loop = asyncio.new_event_loop()
    try:
        with patch("app.services.mediamtx_service.settings") as mock_settings, \
             patch(
                 "app.services.mediamtx_service.MediamtxService._wait_for_api",
                 new_callable=AsyncMock,
                 return_value=False,
             ):
            mock_settings.MEDIAMTX_EXTERNAL = True
            mock_settings.MEDIAMTX_API_URL = "http://mediamtx:9997"
            result = loop.run_until_complete(svc.start())
    finally:
        loop.close()

    assert result is False
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/unit/test_mediamtx_service.py -v -k "external"
```

Expected: FAIL — `start()` doesn't check `MEDIAMTX_EXTERNAL` yet.

**Step 3: Implement external mode in start()**

Replace the `start()` method in `backend/app/services/mediamtx_service.py` with:

```python
    async def start(
        self,
        bin_path: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> bool:
        """
        Launch mediamtx and wait for its REST API to become ready.

        When settings.MEDIAMTX_EXTERNAL is True, skips subprocess launch
        and just verifies the external mediamtx API is reachable (e.g.,
        mediamtx running as a Docker sidecar container).

        Args:
            bin_path:    Override binary path (used in tests).
            config_path: Override config path (used in tests).

        Returns:
            True if mediamtx is running and API is ready, False otherwise.
            FastAPI startup continues regardless of the return value.
        """
        # External mode: skip subprocess, just wait for API
        if settings.MEDIAMTX_EXTERNAL:
            logger.info(
                f"mediamtx external mode: waiting for API at {settings.MEDIAMTX_API_URL}"
            )
            api_ready = await self._wait_for_api(timeout=15.0)
            if api_ready:
                logger.info("mediamtx external API is ready (WebRTC streaming active)")
            else:
                logger.error(
                    "mediamtx external API did not respond within 15 s. "
                    "Is the mediamtx container running?"
                )
            return api_ready

        # Subprocess mode: launch mediamtx binary
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

        # Fast-fail: if the process exited immediately it's a bad config or port conflict.
        await asyncio.sleep(0.1)
        if self._process.poll() is not None:
            logger.error(
                f"mediamtx exited immediately (rc={self._process.returncode}). "
                "Check mediamtx.yml and that ports 9997/8889/8554/8887 are free."
            )
            self._process = None
            return False

        # Wait for the mediamtx REST API to become ready (max 5 s).
        api_ready = await self._wait_for_api(timeout=5.0)

        if not api_ready:
            logger.error(
                "mediamtx started but REST API did not respond within 5 s. "
                "Falling back to HLS streaming."
            )
            self.stop()
            return False

        logger.info("mediamtx is ready (WebRTC streaming active)")
        return True
```

**Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/unit/test_mediamtx_service.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/services/mediamtx_service.py backend/tests/unit/test_mediamtx_service.py
git commit -m "feat(backend): support external mediamtx mode (Docker sidecar)"
```

---

## Task 6: Add check_path_exists to WebRTC Service

**Files:**
- Modify: `backend/app/services/webrtc_service.py`
- Modify: `backend/tests/unit/test_webrtc_service.py`

**Step 1: Write the failing tests**

Add to `backend/tests/unit/test_webrtc_service.py`:

```python
class TestCheckPathExists:
    @pytest.mark.asyncio
    async def test_returns_true_when_path_exists(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "room-1",
            "source": {"type": "rtspSource"},
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await svc.check_path_exists("room-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_path_not_found(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await svc.check_path_exists("room-1")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_connect_error(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            result = await svc.check_path_exists("room-1")
            assert result is False
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/unit/test_webrtc_service.py -v -k "check_path"
```

Expected: FAIL — `check_path_exists` doesn't exist yet.

**Step 3: Implement check_path_exists**

Add to `backend/app/services/webrtc_service.py`, in class `WebRTCService`, after `ensure_path()`:

```python
    async def check_path_exists(self, room_id: str) -> bool:
        """
        Check if a mediamtx path exists (e.g., an RPi is pushing to it).

        Used in push mode where the edge device publishes RTSP to mediamtx
        directly, so no source URL needs to be configured via the API.

        Args:
            room_id: Path name in mediamtx (matches the room UUID).

        Returns:
            True if the path exists on mediamtx, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.MEDIAMTX_API_URL}/v3/paths/get/{room_id}",
                )
                return resp.status_code == 200
        except httpx.ConnectError:
            logger.error(
                f"WebRTC: cannot reach mediamtx at {settings.MEDIAMTX_API_URL} "
                f"— is mediamtx running? (room={room_id})"
            )
            return False
        except Exception as exc:
            logger.error(f"WebRTC: error checking path {room_id}: {exc}")
            return False
```

**Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/unit/test_webrtc_service.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/services/webrtc_service.py backend/tests/unit/test_webrtc_service.py
git commit -m "feat(backend): add check_path_exists for push-mode WebRTC"
```

---

## Task 7: Handle Push Mode in Live Stream WebSocket

**Files:**
- Modify: `backend/app/routers/live_stream.py:140-198`

The current code exits early if `rtsp_url is None` (line 142-149). In push mode (RPi pushes to mediamtx), there's no RTSP URL configured on the room, but the stream is available via mediamtx. We need to allow WebRTC to work without a camera URL.

**Step 1: Modify the rtsp_url check to allow push mode**

Replace lines 140-198 in `live_stream.py` (from `rtsp_url = get_camera_url(...)` through the mode selection) with:

```python
        room_id = str(schedule.room_id)
        rtsp_url = get_camera_url(room_id, db)

        # In push mode (RPi → mediamtx), rtsp_url may be None.
        # Only error out if WebRTC is also unavailable.
        if rtsp_url is None and not settings.USE_WEBRTC_STREAMING:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "No camera configured for this room",
            })
            await websocket.close(code=4003, reason="No camera configured")
            return
```

Then replace the mode-selection block (lines 169-198) with:

```python
    # Determine stream mode, with automatic fallback.
    use_webrtc = False
    if settings.USE_WEBRTC_STREAMING:
        if rtsp_url:
            # Pull mode: tell mediamtx to pull from the camera RTSP URL
            mediamtx_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
        else:
            # Push mode: RPi pushes RTSP to mediamtx, just check path exists
            mediamtx_ok = await webrtc_service.check_path_exists(room_id)
        if mediamtx_ok:
            use_webrtc = True
        else:
            if rtsp_url:
                logger.warning(
                    f"Live stream: mediamtx unreachable, falling back to "
                    f"{'HLS' if settings.USE_HLS_STREAMING else 'legacy'} "
                    f"for room {room_id}"
                )
            else:
                logger.warning(
                    f"Live stream: no RTSP URL and mediamtx path not found "
                    f"for room {room_id} — is the edge device streaming?"
                )

    # If WebRTC failed and we have no rtsp_url, there's nothing to stream
    if not use_webrtc and rtsp_url is None:
        await websocket.send_json({
            "type": "error",
            "message": "Camera stream not available — edge device may not be active",
        })
        await websocket.close(code=4003, reason="No stream available")
        return
```

**Step 2: Run existing tests to check for regressions**

```bash
cd backend
pytest tests/ -v -k "live_stream or stream" --timeout=30
```

Expected: PASS (or skip if no live_stream tests exist)

**Step 3: Commit**

```bash
git add backend/app/routers/live_stream.py
git commit -m "feat(backend): support push-mode WebRTC in live stream (no RTSP URL needed)"
```

---

## Task 8: Handle Push Mode in WebRTC Router

**Files:**
- Modify: `backend/app/routers/webrtc.py:103-118`

**Step 1: Update the offer endpoint for push mode**

Replace lines 103-118 in `webrtc.py` (from `# 3. Resolve camera RTSP URL` through `ensure_path`) with:

```python
    # 3. Resolve camera RTSP URL (may be None in push mode)
    room_id = str(schedule.room_id)
    rtsp_url = get_camera_url(room_id, db)

    # 4. Ensure mediamtx path exists
    if rtsp_url:
        # Pull mode: tell mediamtx to pull from camera RTSP URL
        path_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
    else:
        # Push mode: RPi pushes RTSP to mediamtx, just check path exists
        path_ok = await webrtc_service.check_path_exists(room_id)

    if not path_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebRTC stream unavailable — is the edge device streaming?",
        )
```

**Step 2: Run existing tests**

```bash
cd backend
pytest tests/integration/test_webrtc_router.py -v --timeout=30
```

Expected: PASS (or skip)

**Step 3: Commit**

```bash
git add backend/app/routers/webrtc.py
git commit -m "feat(backend): support push-mode WebRTC in offer endpoint"
```

---

## Task 9: Update Backend Production Environment

**Files:**
- Modify: `backend/.env.production`

**Step 1: Enable WebRTC with external mediamtx**

Replace the streaming section at the bottom of `backend/.env.production` with:

```bash
# ===== Streaming (WebRTC via mediamtx Docker sidecar) =====
USE_HLS_STREAMING=false
USE_WEBRTC_STREAMING=true
MEDIAMTX_EXTERNAL=true
MEDIAMTX_API_URL=http://mediamtx:9997
MEDIAMTX_WEBRTC_URL=http://mediamtx:8889
DEFAULT_RTSP_URL=
RECOGNITION_RTSP_URL=
```

Note: `mediamtx` is the Docker service name, resolved via Docker's internal DNS.

**Step 2: Commit**

```bash
git add backend/.env.production
git commit -m "feat(backend): enable WebRTC streaming with external mediamtx in production"
```

---

## Task 10: Create Production mediamtx Config

**Files:**
- Create: `deploy/mediamtx.yml`

**Step 1: Create the production mediamtx config**

```yaml
# mediamtx production configuration for IAMS (Docker on VPS)
#
# Receives RTSP push from RPi edge devices and serves WebRTC (WHEP) to
# mobile clients. FastAPI proxies WHEP signaling; media flows directly
# from mediamtx to phones via WebRTC UDP.

logLevel: warn

# REST API — used by FastAPI backend container to manage paths
# Listens on all interfaces so the backend container can reach it
# via Docker network (http://mediamtx:9997).
api: yes
apiAddress: :9997

# RTSP — receives push from RPi edge devices over the internet.
# RPi runs: ffmpeg -i rtsp://camera/sub -c copy -f rtsp rtsp://VPS:8554/room-{id}
rtsp: yes
rtspAddress: :8554

# WebRTC (WHEP) — FastAPI proxies WHEP offers here.
# Mobile clients negotiate via POST /api/v1/webrtc/{schedule_id}/offer
# which forwards to http://mediamtx:8889/{room_id}/whep.
webrtc: yes
webrtcAddress: :8889

# ICE: tell clients to connect to the VPS public IP for media.
# Without this, ICE candidates would use the container's private IP
# which is unreachable from the internet.
webrtcICEHostNAT1To1IPs:
  - 167.71.217.44

# Explicit UDP port for WebRTC media (must match docker-compose port mapping).
webrtcLocalUDPAddress: :8887

# Disable unused protocols
hls: no
srt: no
rtmp: no

# Paths are created automatically when RPi pushes RTSP.
# No static path config needed.
paths: {}
```

**Step 2: Commit**

```bash
git add deploy/mediamtx.yml
git commit -m "feat(deploy): add production mediamtx config for WebRTC streaming"
```

---

## Task 11: Add mediamtx Service to Docker Compose

**Files:**
- Modify: `deploy/docker-compose.prod.yml`

**Step 1: Add mediamtx service**

Add the mediamtx service after the `backend` service (before `nginx`):

```yaml
  mediamtx:
    image: bluenviron/mediamtx:latest
    container_name: iams-mediamtx
    restart: unless-stopped
    volumes:
      - ./mediamtx.yml:/mediamtx.yml:ro
    ports:
      # RTSP ingest from RPi edge devices (over internet)
      - "8554:8554"
      # WebRTC media UDP (ICE candidates point here)
      - "8887:8887/udp"
    # API (9997) and WHEP (8889) are internal only — accessed
    # by backend and nginx via Docker network, not exposed to host.
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:9997/v3/config/global/get"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
```

**Step 2: Make backend depend on mediamtx**

Update the `nginx` service's `depends_on` to also wait for mediamtx:

```yaml
  nginx:
    image: nginx:alpine
    container_name: iams-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - certbot_certs:/etc/letsencrypt:ro
      - certbot_www:/var/www/certbot:ro
    depends_on:
      backend:
        condition: service_healthy
      mediamtx:
        condition: service_healthy
```

**Step 3: Commit**

```bash
git add deploy/docker-compose.prod.yml
git commit -m "feat(deploy): add mediamtx sidecar container for WebRTC streaming"
```

---

## Task 12: Update Deploy Script and Firewall

**Files:**
- Modify: `deploy/deploy.sh`

**Step 1: Add mediamtx config sync to deploy.sh**

In `deploy/deploy.sh`, update Step 2 to also sync `mediamtx.yml`:

```bash
# Step 2: Sync deploy configs
echo "[2/4] Syncing deploy configs..."
rsync -avz \
    "${PROJECT_DIR}/deploy/docker-compose.prod.yml" \
    "${PROJECT_DIR}/deploy/nginx.conf" \
    "${PROJECT_DIR}/deploy/mediamtx.yml" \
    "${VPS_USER}@${VPS_IP}:${VPS_DIR}/deploy/"
```

**Step 2: Add firewall rules to the VPS SSH block**

In the SSH remote block (Step 3), add firewall commands before `docker compose build`:

```bash
    # Open ports for mediamtx (if not already open)
    echo "Checking firewall rules..."
    ufw allow 8554/tcp comment "mediamtx RTSP ingest from RPi" 2>/dev/null || true
    ufw allow 8887/udp comment "mediamtx WebRTC media" 2>/dev/null || true
```

**Step 3: Commit**

```bash
git add deploy/deploy.sh
git commit -m "feat(deploy): sync mediamtx config and open firewall ports"
```

---

## Task 13: End-to-End Verification

**Step 1: Deploy to VPS**

```bash
bash deploy/deploy.sh
```

**Step 2: Verify mediamtx is running on VPS**

```bash
ssh root@167.71.217.44 'cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml ps'
```

Expected: `iams-mediamtx` shows `Up (healthy)`

**Step 3: Verify mediamtx API is reachable from backend**

```bash
ssh root@167.71.217.44 'docker exec iams-backend curl -s http://mediamtx:9997/v3/config/global/get | head -c 100'
```

Expected: JSON response (mediamtx config)

**Step 4: Verify RTSP port is open**

```bash
ssh root@167.71.217.44 'ufw status | grep 8554'
```

Expected: `8554/tcp ALLOW Anywhere`

**Step 5: Configure edge device**

On the RPi, update `edge/.env`:

```bash
STREAM_RELAY_ENABLED=true
STREAM_RELAY_URL=rtsp://167.71.217.44:8554
```

Then restart the edge device:

```bash
cd /opt/iams/edge
sudo systemctl restart iams-edge  # or: python run.py
```

**Step 6: Verify stream appears on mediamtx**

When a session is active:

```bash
ssh root@167.71.217.44 'docker exec iams-mediamtx wget -q -O - http://localhost:9997/v3/paths/list | python3 -m json.tool'
```

Expected: Shows path `room-{room_id}` with an active reader/source.

**Step 7: Test in mobile app**

1. Start an attendance session as faculty
2. Open Live Feed screen
3. Should see real-time video with detection overlays

---

## Summary of All Changes

| Component | File | Change |
|-----------|------|--------|
| Edge | `edge/app/config.py` | Add `STREAM_RELAY_ENABLED`, `STREAM_RELAY_URL`, `STREAM_RELAY_RETRY_DELAY` |
| Edge | `edge/.env.example` | Document stream relay env vars |
| Edge | `edge/app/stream_relay.py` | **New** — FFmpeg subprocess manager |
| Edge | `edge/app/main.py` | Integrate stream relay into session lifecycle |
| Backend | `backend/app/config.py` | Add `MEDIAMTX_EXTERNAL` setting |
| Backend | `backend/app/services/mediamtx_service.py` | Support external mediamtx (skip subprocess) |
| Backend | `backend/app/services/webrtc_service.py` | Add `check_path_exists()` for push mode |
| Backend | `backend/app/routers/live_stream.py` | Handle push mode (no RTSP URL needed) |
| Backend | `backend/app/routers/webrtc.py` | Handle push mode in offer endpoint |
| Backend | `backend/.env.production` | Enable `USE_WEBRTC_STREAMING`, `MEDIAMTX_EXTERNAL` |
| Backend | `backend/tests/unit/test_mediamtx_service.py` | Tests for external mode |
| Backend | `backend/tests/unit/test_webrtc_service.py` | Tests for `check_path_exists` |
| Deploy | `deploy/mediamtx.yml` | **New** — production mediamtx config |
| Deploy | `deploy/docker-compose.prod.yml` | Add mediamtx sidecar service |
| Deploy | `deploy/deploy.sh` | Sync mediamtx.yml, open firewall ports |
