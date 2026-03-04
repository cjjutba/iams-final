# WebRTC Live Feed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the HLS live feed with WebRTC via mediamtx to achieve <300ms latency on LAN, with STUN/TURN for production multi-network use.

**Architecture:** mediamtx (single binary) runs alongside FastAPI, pulls the Reolink RTSP stream, and serves it via WebRTC using the WHEP protocol. FastAPI acts as the secure signaling proxy — mobile clients never talk to mediamtx directly. The detection metadata WebSocket is unchanged; only the video transport changes.

**Tech Stack:** mediamtx v1.11+, react-native-webrtc, httpx (already installed), WHEP (WebRTC HTTP Egress Protocol), Pydantic v2 settings, pytest + respx (for mocking httpx).

---

## Codebase Context (read before starting any task)

```
backend/app/
├── config.py                     # Pydantic settings — add WEBRTC_* fields here
├── main.py                       # Register new webrtc router ~line 371
├── routers/
│   ├── live_stream.py            # Add _webrtc_mode(), update live_stream_ws()
│   └── webrtc.py                 # NEW: GET /config, POST /{schedule_id}/offer
├── services/
│   ├── camera_config.py          # get_camera_url(room_id, db) — reuse as-is
│   └── webrtc_service.py         # NEW: mediamtx path management + WHEP proxy
└── schemas/
    └── webrtc.py                 # NEW: WebRTCOfferRequest schema

mobile/src/
├── hooks/
│   ├── useDetectionWebSocket.ts  # Add streamMode to return value
│   └── useWebRTC.ts              # NEW: RTCPeerConnection + WHEP signaling
└── screens/faculty/
    └── FacultyLiveFeedScreen.tsx # Replace VideoView with RTCView
```

**Existing patterns to follow:**
- Router auth: `current_user: User = Depends(get_current_user)`, `db: Session = Depends(get_db)` — see `schedules.py`
- HTTP client: `httpx.AsyncClient` — already in requirements.txt (v0.28.1)
- Test mocking: `unittest.mock.patch`, `AsyncMock` — see existing integration tests
- Mobile hooks: exponential backoff pattern — see `useDetectionWebSocket.ts:246-258`
- Config: pydantic-settings `BaseSettings` — see `config.py`

**Current priority order for streaming mode (add to live_stream_ws):**
```
USE_WEBRTC_STREAMING → True  → _webrtc_mode()
USE_HLS_STREAMING    → True  → _hls_mode()    (existing)
else                          → _legacy_mode() (existing)
```

---

## Task 1: WebRTC Config Defaults

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/tests/unit/test_config_webrtc.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_config_webrtc.py
"""Tests for WebRTC configuration defaults."""
import pytest
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
```

**Step 2: Run test to verify it fails**

```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_config_webrtc.py -v
```

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'USE_WEBRTC_STREAMING'`

**Step 3: Add the config fields**

Open `backend/app/config.py`. Find the HLS streaming block (around line 73-76) and add the new fields directly below the HLS block:

```python
    # WebRTC Streaming (mediamtx + WHEP — replaces HLS for <300ms latency)
    USE_WEBRTC_STREAMING: bool = True                        # True=WebRTC, False=fall back to HLS/legacy
    MEDIAMTX_API_URL: str = "http://localhost:9997"          # mediamtx REST API (internal only)
    MEDIAMTX_WEBRTC_URL: str = "http://localhost:8889"       # mediamtx WHEP endpoint (internal only)
    WEBRTC_STUN_URLS: str = "stun:stun.l.google.com:19302"  # Comma-separated STUN URLs (free Google STUN)
    WEBRTC_TURN_URL: str = ""                                # Optional: "turn:your-server:3478"
    WEBRTC_TURN_USERNAME: str = ""                           # TURN username (empty = no TURN)
    WEBRTC_TURN_CREDENTIAL: str = ""                         # TURN credential
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_config_webrtc.py -v
```

Expected: 6 passed

**Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/unit/test_config_webrtc.py
git commit -m "feat(webrtc): add WebRTC config fields — mediamtx URLs, STUN/TURN settings"
```

---

## Task 2: mediamtx Configuration File

**Files:**
- Create: `backend/mediamtx.yml`
- Create: `backend/scripts/start_mediamtx.sh`

No unit test for this task — it's a config file. Validation is manual (mediamtx startup).

**Step 1: Download mediamtx binary**

Go to https://github.com/bluenviron/mediamtx/releases and download the binary for your OS:

- **macOS Apple Silicon (M1/M2/M3):** `mediamtx_v1.11.3_darwin_arm64.tar.gz`
- **macOS Intel:** `mediamtx_v1.11.3_darwin_amd64.tar.gz`
- **Linux amd64 (server):** `mediamtx_v1.11.3_linux_amd64.tar.gz`
- **Linux arm64 (Raspberry Pi 4):** `mediamtx_v1.11.3_linux_arm64v8.tar.gz`

Extract and place the `mediamtx` binary in `backend/bin/mediamtx` (create the `bin/` directory if it doesn't exist). Add it to `.gitignore` since binaries shouldn't be committed:

```bash
echo "backend/bin/mediamtx" >> .gitignore
echo "backend/bin/mediamtx.exe" >> .gitignore
```

**Step 2: Create mediamtx.yml**

```yaml
# backend/mediamtx.yml
# mediamtx configuration for IAMS WebRTC live feed.
# Run: ./bin/mediamtx mediamtx.yml  (from backend/ directory)
# Docs: https://github.com/bluenviron/mediamtx

###############################################################################
# General
###############################################################################
logLevel: info
logDestinations: [stdout]

###############################################################################
# RTSP server (mediamtx receives camera RTSP, re-serves internally)
###############################################################################
rtspAddress: :8554

###############################################################################
# WebRTC / WHEP endpoint
# Mobile app connects here (via FastAPI proxy — never directly exposed)
###############################################################################
webrtcAddress: :8889
webrtcEncryption: no          # TLS handled by nginx in production
webrtcLocalUDPAddress: :8888  # ICE UDP port (open in firewall for production)
webrtcIPsFromInterfaces: yes  # Auto-detect local IPs for ICE candidates
webrtcIPsFromInterfacesList: []
webrtcAdditionalHosts: []     # Add public IP here in production if needed
webrtcICEServers2:
  - urls: [stun:stun.l.google.com:19302]
  # Uncomment and fill in for production TURN (needed for cellular clients):
  # - urls: [turn:your-turn-server:3478]
  #   username: your-username
  #   credential: your-password

###############################################################################
# REST API (used by FastAPI webrtc_service to manage paths dynamically)
###############################################################################
api: yes
apiAddress: :9997    # Internal only — do NOT expose this port to the internet
apiEncryption: no

###############################################################################
# Path defaults
# Paths are created dynamically by FastAPI via the REST API.
# auth is handled by FastAPI before forwarding to WHEP — mediamtx trusts internal calls.
###############################################################################
paths:
  all_others:
    readAnyUser: yes   # FastAPI already validated JWT before calling WHEP
    readAnyPass: ""
    sourceOnDemand: yes
```

**Step 3: Create convenience startup script**

```bash
#!/usr/bin/env bash
# backend/scripts/start_mediamtx.sh
# Run mediamtx alongside FastAPI for local development.
# Usage: ./scripts/start_mediamtx.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BINARY="$SCRIPT_DIR/bin/mediamtx"
CONFIG="$SCRIPT_DIR/mediamtx.yml"

if [ ! -f "$BINARY" ]; then
  echo "ERROR: mediamtx binary not found at $BINARY"
  echo "Download from https://github.com/bluenviron/mediamtx/releases"
  exit 1
fi

echo "Starting mediamtx..."
exec "$BINARY" "$CONFIG"
```

```bash
chmod +x backend/scripts/start_mediamtx.sh
```

**Step 4: Verify mediamtx starts**

```bash
cd backend
./bin/mediamtx mediamtx.yml
```

Expected output:
```
INF MediaMTX v1.11.x
INF [RTSP] listener opened on :8554 (TCP), :8000 (UDP/RTP), :8001 (UDP/RTCP)
INF [WebRTC] listener opened on :8889 (HTTP)
INF [API] listener opened on :9997
```

Press `Ctrl+C` to stop (it will be started alongside FastAPI for real usage).

**Step 5: Commit**

```bash
git add backend/mediamtx.yml backend/scripts/start_mediamtx.sh .gitignore
git commit -m "feat(webrtc): add mediamtx config and startup script"
```

---

## Task 3: WebRTC Service (Backend)

**Files:**
- Create: `backend/app/services/webrtc_service.py`
- Create: `backend/tests/unit/test_webrtc_service.py`

**Step 1: Write the failing tests**

```python
# backend/tests/unit/test_webrtc_service.py
"""Tests for WebRTCService — mediamtx path management and WHEP proxy."""
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_settings():
    with patch("app.services.webrtc_service.settings") as mock:
        mock.MEDIAMTX_API_URL = "http://localhost:9997"
        mock.MEDIAMTX_WEBRTC_URL = "http://localhost:8889"
        mock.WEBRTC_STUN_URLS = "stun:stun.l.google.com:19302"
        mock.WEBRTC_TURN_URL = ""
        mock.WEBRTC_TURN_USERNAME = ""
        mock.WEBRTC_TURN_CREDENTIAL = ""
        yield mock


class TestGetIceServers:
    def test_returns_stun_server(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()
        servers = svc.get_ice_servers()
        assert len(servers) == 1
        assert servers[0]["urls"] == ["stun:stun.l.google.com:19302"]

    def test_includes_turn_when_configured(self, mock_settings):
        mock_settings.WEBRTC_TURN_URL = "turn:my-turn.example.com:3478"
        mock_settings.WEBRTC_TURN_USERNAME = "user"
        mock_settings.WEBRTC_TURN_CREDENTIAL = "pass"
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()
        servers = svc.get_ice_servers()
        assert len(servers) == 2
        turn = servers[1]
        assert turn["urls"] == ["turn:my-turn.example.com:3478"]
        assert turn["username"] == "user"
        assert turn["credential"] == "pass"

    def test_multiple_stun_urls(self, mock_settings):
        mock_settings.WEBRTC_STUN_URLS = (
            "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302"
        )
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()
        servers = svc.get_ice_servers()
        assert len(servers[0]["urls"]) == 2


class TestEnsurePath:
    @pytest.mark.asyncio
    async def test_creates_new_path(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await svc.ensure_path("room-1", "rtsp://cam/stream")
            assert result is True

    @pytest.mark.asyncio
    async def test_patches_existing_path(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        conflict_response = MagicMock()
        conflict_response.status_code = 400  # Already exists
        ok_response = MagicMock()
        ok_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=conflict_response)
            mock_client.patch = AsyncMock(return_value=ok_response)
            mock_client_cls.return_value = mock_client

            result = await svc.ensure_path("room-1", "rtsp://cam/stream")
            assert result is True
            mock_client.patch.assert_called_once()


class TestForwardWhepOffer:
    @pytest.mark.asyncio
    async def test_returns_sdp_answer(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n"
        mock_response.headers = {"Location": "/session/abc123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            answer, resource = await svc.forward_whep_offer("room-1", "v=0\r\n...")
            assert "v=0" in answer
            assert resource == "/session/abc123"


class TestDeletePath:
    @pytest.mark.asyncio
    async def test_deletes_path(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Should not raise
            await svc.delete_path("room-1")
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_swallows_delete_errors(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.delete = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            # Should not raise — cleanup errors are non-fatal
            await svc.delete_path("room-1")
```

**Step 2: Run to verify they fail**

```bash
pytest tests/unit/test_webrtc_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.webrtc_service'`

**Step 3: Create the service**

```python
# backend/app/services/webrtc_service.py
"""
WebRTC Service

Manages mediamtx path lifecycle and proxies WebRTC WHEP signaling.
mediamtx is a single binary that bridges RTSP → WebRTC (WHEP protocol).

FastAPI calls this service to:
1. Create a mediamtx path for a room (source = camera RTSP URL)
2. Forward the mobile app's SDP offer to mediamtx's WHEP endpoint
3. Return the SDP answer to the mobile app
4. Clean up paths when no longer needed
"""

import httpx

from app.config import settings, logger


class WebRTCService:
    """Thin adapter over the mediamtx HTTP API and WHEP endpoint."""

    def get_ice_servers(self) -> list[dict]:
        """
        Build the ICE server list from settings.

        Returns a list ready to pass into RTCPeerConnection({ iceServers }).
        Always includes STUN; optionally includes TURN when configured.
        """
        stun_urls = [
            u.strip()
            for u in settings.WEBRTC_STUN_URLS.split(",")
            if u.strip()
        ]
        servers: list[dict] = [{"urls": stun_urls}]

        if settings.WEBRTC_TURN_URL:
            servers.append({
                "urls": [settings.WEBRTC_TURN_URL],
                "username": settings.WEBRTC_TURN_USERNAME,
                "credential": settings.WEBRTC_TURN_CREDENTIAL,
            })

        return servers

    async def ensure_path(self, room_id: str, rtsp_url: str) -> bool:
        """
        Create (or update) a mediamtx path that pulls from the camera RTSP URL.

        mediamtx will start pulling from rtsp_url on demand (when a viewer connects).

        Args:
            room_id:  Path name in mediamtx (matches the room UUID).
            rtsp_url: RTSP source URL of the camera.

        Returns:
            True on success, False if mediamtx is unreachable.
        """
        payload = {
            "source": rtsp_url,
            "sourceOnDemand": True,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{settings.MEDIAMTX_API_URL}/v3/config/paths/add/{room_id}",
                    json=payload,
                )
                if resp.status_code == 400:
                    # Path already exists — patch it with the latest RTSP URL
                    resp = await client.patch(
                        f"{settings.MEDIAMTX_API_URL}/v3/config/paths/patch/{room_id}",
                        json=payload,
                    )
                ok = resp.status_code in (200, 201, 204)
                if not ok:
                    logger.error(
                        f"WebRTC: mediamtx path create/patch failed "
                        f"(room={room_id}, status={resp.status_code}): {resp.text}"
                    )
                return ok
        except httpx.ConnectError:
            logger.error(
                f"WebRTC: cannot reach mediamtx at {settings.MEDIAMTX_API_URL} "
                f"— is mediamtx running? (room={room_id})"
            )
            return False
        except Exception as exc:
            logger.error(f"WebRTC: unexpected error ensuring path for room {room_id}: {exc}")
            return False

    async def forward_whep_offer(
        self, room_id: str, sdp: str
    ) -> tuple[str, str]:
        """
        Forward the mobile app's SDP offer to mediamtx's WHEP endpoint.

        WHEP (WebRTC HTTP Egress Protocol) uses plain-text SDP bodies:
        - Request: POST /{path}/whep  Content-Type: application/sdp  body=offer_sdp
        - Response: 201 Created        Content-Type: application/sdp  body=answer_sdp
                    Location: <resource URL for teardown>

        Args:
            room_id: mediamtx path name (= room UUID).
            sdp:     SDP offer string from the mobile RTCPeerConnection.

        Returns:
            Tuple of (answer_sdp, resource_url).

        Raises:
            httpx.HTTPStatusError: if mediamtx rejects the offer.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.MEDIAMTX_WEBRTC_URL}/{room_id}/whep",
                content=sdp,
                headers={"Content-Type": "application/sdp"},
            )
            resp.raise_for_status()
            resource_url = resp.headers.get("Location", "")
            return resp.text, resource_url

    async def delete_path(self, room_id: str) -> None:
        """
        Remove a mediamtx path. Called when the last viewer disconnects.

        Errors are swallowed — cleanup failures are non-fatal.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(
                    f"{settings.MEDIAMTX_API_URL}/v3/config/paths/delete/{room_id}"
                )
        except Exception as exc:
            logger.warning(f"WebRTC: failed to delete mediamtx path {room_id}: {exc}")


# Module-level singleton
webrtc_service = WebRTCService()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_webrtc_service.py -v
```

Expected: 9 passed

**Step 5: Commit**

```bash
git add backend/app/services/webrtc_service.py backend/tests/unit/test_webrtc_service.py
git commit -m "feat(webrtc): add WebRTCService — mediamtx path management and WHEP proxy"
```

---

## Task 4: WebRTC Router + Schemas (Backend)

**Files:**
- Create: `backend/app/schemas/webrtc.py`
- Create: `backend/app/routers/webrtc.py`
- Modify: `backend/app/main.py` (~line 371, after HLS router block)
- Create: `backend/tests/integration/test_webrtc_router.py`

**Step 1: Write the failing tests**

```python
# backend/tests/integration/test_webrtc_router.py
"""Integration tests for the WebRTC router."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client(test_app, db_session):
    return TestClient(test_app)


class TestGetWebRTCConfig:
    def test_returns_ice_servers(self, client):
        with patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_svc.get_ice_servers.return_value = [
                {"urls": ["stun:stun.l.google.com:19302"]}
            ]
            resp = client.get("/api/v1/webrtc/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]["ice_servers"]) >= 1
        assert "urls" in data["data"]["ice_servers"][0]


class TestWebRTCOffer:
    def test_requires_auth(self, client):
        resp = client.post("/api/v1/webrtc/some-schedule-id/offer",
                           json={"sdp": "v=0\r\n", "type": "offer"})
        assert resp.status_code == 401

    def test_returns_404_for_unknown_schedule(self, client, auth_headers):
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = None
            resp = client.post(
                "/api/v1/webrtc/nonexistent-schedule/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_returns_503_when_no_camera(self, client, auth_headers, sample_schedule):
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value=None):
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "camera" in resp.json()["detail"].lower()

    def test_returns_503_when_mediamtx_down(self, client, auth_headers, sample_schedule):
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value="rtsp://cam/stream"), \
             patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            mock_svc.ensure_path = AsyncMock(return_value=False)
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "webrtc" in resp.json()["detail"].lower()

    def test_returns_sdp_answer_on_success(self, client, auth_headers, sample_schedule):
        fake_answer = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n"
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value="rtsp://cam/stream"), \
             patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            mock_svc.ensure_path = AsyncMock(return_value=True)
            mock_svc.forward_whep_offer = AsyncMock(return_value=(fake_answer, "/session/x"))
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["type"] == "answer"
        assert "v=0" in body["data"]["sdp"]
```

**Step 2: Run to verify they fail**

```bash
pytest tests/integration/test_webrtc_router.py -v
```

Expected: FAIL with `ModuleNotFoundError` or 404 (router not registered yet)

**Step 3: Create schemas**

```python
# backend/app/schemas/webrtc.py
"""Pydantic schemas for WebRTC signaling endpoints."""
from pydantic import BaseModel


class WebRTCOfferRequest(BaseModel):
    """SDP offer from the mobile RTCPeerConnection."""
    sdp: str
    type: str = "offer"
```

**Step 4: Create the router**

```python
# backend/app/routers/webrtc.py
"""
WebRTC Router

Secure signaling proxy between the mobile app and mediamtx.
Mobile clients never talk to mediamtx directly — FastAPI validates
the JWT token and proxies the WHEP offer/answer.

Endpoints:
    GET  /api/v1/webrtc/config                — ICE server list (STUN/TURN)
    POST /api/v1/webrtc/{schedule_id}/offer   — WHEP signaling proxy
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import logger
from app.database import get_db
from app.models.user import User
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.webrtc import WebRTCOfferRequest
from app.services.camera_config import get_camera_url
from app.services.webrtc_service import webrtc_service
from app.utils.dependencies import get_current_user

router = APIRouter()


@router.get("/config")
async def get_webrtc_config():
    """
    Get ICE server configuration for WebRTC peer connections.

    Returns STUN and optional TURN server details from backend config.
    Mobile app calls this before creating RTCPeerConnection.
    No authentication required (ICE config is not sensitive).
    """
    ice_servers = webrtc_service.get_ice_servers()
    return {
        "success": True,
        "data": {"ice_servers": ice_servers},
    }


@router.post("/{schedule_id}/offer")
async def create_webrtc_offer(
    schedule_id: str,
    body: WebRTCOfferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Forward WebRTC SDP offer to mediamtx WHEP endpoint.

    Flow:
      1. Validate schedule exists
      2. Resolve room → RTSP camera URL
      3. Ensure mediamtx path exists for this room
      4. Forward SDP offer to mediamtx WHEP endpoint
      5. Return SDP answer to mobile app

    The mobile app then calls setRemoteDescription(answer) to complete
    the WebRTC handshake and start streaming.

    Requires: valid JWT token (any authenticated user)
    """
    # 1. Validate schedule
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule not found: {schedule_id}",
        )

    # 2. Resolve camera RTSP URL
    room_id = str(schedule.room_id)
    rtsp_url = get_camera_url(room_id, db)
    if rtsp_url is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No camera configured for this room",
        )

    # 3. Ensure mediamtx path exists (creates or updates)
    path_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
    if not path_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebRTC service unavailable — is mediamtx running?",
        )

    # 4. Forward SDP offer to mediamtx WHEP
    try:
        answer_sdp, _ = await webrtc_service.forward_whep_offer(room_id, body.sdp)
    except httpx.HTTPStatusError as exc:
        logger.error(f"WHEP offer failed for room {room_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebRTC stream unavailable — camera may be offline",
        )
    except Exception as exc:
        logger.error(f"Unexpected WHEP error for room {room_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during WebRTC setup",
        )

    # 5. Return SDP answer
    logger.info(
        f"WebRTC offer forwarded: schedule={schedule_id}, room={room_id}, "
        f"user={current_user.id}"
    )
    return {
        "success": True,
        "data": {
            "sdp": answer_sdp,
            "type": "answer",
        },
    }
```

**Step 5: Register the router in main.py**

Open `backend/app/main.py`. Find the HLS router block (around line 371):

```python
# HLS routes (serve .m3u8 playlists and .ts segments)
if settings.USE_HLS_STREAMING:
    app.include_router(
        hls.router,
        prefix=f"{settings.API_PREFIX}/hls",
        tags=["HLS Streaming"]
    )
```

Add the import at the top of the file alongside the other router imports (line ~27):
```python
from app.routers import auth, users, face, schedules, attendance, websocket, notifications, presence, live_stream, hls, webrtc
```

Add the router registration directly after the HLS block:
```python
# WebRTC routes (WHEP signaling proxy + ICE config)
if settings.USE_WEBRTC_STREAMING:
    app.include_router(
        webrtc.router,
        prefix=f"{settings.API_PREFIX}/webrtc",
        tags=["WebRTC Streaming"]
    )
```

**Step 6: Run tests to verify they pass**

```bash
pytest tests/integration/test_webrtc_router.py -v
```

Expected: 5 passed

Also run the full suite to check nothing broke:

```bash
pytest --tb=short -q 2>&1 | tail -10
```

Expected: All previous tests pass + new 5 tests.

**Step 7: Commit**

```bash
git add backend/app/schemas/webrtc.py backend/app/routers/webrtc.py \
        backend/app/main.py backend/tests/integration/test_webrtc_router.py
git commit -m "feat(webrtc): add WebRTC router — /config and /{schedule_id}/offer endpoints"
```

---

## Task 5: WebSocket _webrtc_mode (Backend)

**Files:**
- Modify: `backend/app/routers/live_stream.py`
- Create: `backend/tests/unit/test_live_stream_webrtc_mode.py`

**Context:** `live_stream.py` currently has `_hls_mode()` and `_legacy_mode()`. We add `_webrtc_mode()` which is like `_hls_mode()` but without HLS service calls. The WebSocket still delivers detection metadata; video comes from WebRTC separately.

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_live_stream_webrtc_mode.py
"""Tests for the WebSocket live_stream_ws routing to _webrtc_mode."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestLiveStreamWebRTCRouting:
    @pytest.mark.asyncio
    async def test_webrtc_connected_message_has_no_hls_url(self):
        """In WebRTC mode the connected message omits hls_url."""
        from app.routers.live_stream import _webrtc_mode
        from starlette.websockets import WebSocketState

        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        sent_messages = []
        ws.send_json = AsyncMock(side_effect=lambda m: sent_messages.append(m))

        async def stop_after_connected(*args, **kwargs):
            raise Exception("stop")

        with patch("app.routers.live_stream.recognition_service") as mock_recog, \
             patch("app.routers.live_stream.settings") as mock_settings:
            mock_settings.RECOGNITION_RTSP_URL = ""
            mock_settings.STREAM_FPS = 10
            mock_settings.STREAM_WIDTH = 1280
            mock_settings.STREAM_HEIGHT = 720
            mock_recog.start = AsyncMock(return_value=True)
            mock_recog.get_latest_detections = MagicMock(side_effect=stop_after_connected)

            try:
                await _webrtc_mode(ws, "v1", "sched-1", "room-1", "rtsp://cam")
            except Exception:
                pass

        connected = next(m for m in sent_messages if m.get("type") == "connected")
        assert connected["mode"] == "webrtc"
        assert "hls_url" not in connected

    @pytest.mark.asyncio
    async def test_webrtc_mode_does_not_start_hls_service(self):
        """_webrtc_mode must never call hls_service.start_stream."""
        from app.routers.live_stream import _webrtc_mode
        from starlette.websockets import WebSocketState

        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        with patch("app.routers.live_stream.recognition_service") as mock_recog, \
             patch("app.routers.live_stream.settings") as mock_settings, \
             patch("app.routers.live_stream.hls_service", None) as mock_hls:
            mock_settings.RECOGNITION_RTSP_URL = ""
            mock_settings.STREAM_FPS = 10
            mock_settings.STREAM_WIDTH = 1280
            mock_settings.STREAM_HEIGHT = 720
            mock_recog.start = AsyncMock(return_value=False)
            mock_recog.get_latest_detections = MagicMock(return_value=None)
            mock_recog.stop = AsyncMock()

            # Disconnect immediately
            ws.receive_json = AsyncMock(side_effect=Exception("disconnect"))

            try:
                await _webrtc_mode(ws, "v1", "sched-1", "room-1", "rtsp://cam")
            except Exception:
                pass

        # hls_service was not imported inside _webrtc_mode
        assert mock_hls is None  # hls_service patch was never accessed
```

**Step 2: Run to verify they fail**

```bash
pytest tests/unit/test_live_stream_webrtc_mode.py -v
```

Expected: FAIL with `ImportError` (no `_webrtc_mode` function yet)

**Step 3: Add `_webrtc_mode` to live_stream.py**

Open `backend/app/routers/live_stream.py`. After the `_hls_mode` function (around line 320), add:

```python
# ---------------------------------------------------------------------------
# WebRTC mode: metadata-only WebSocket (video via mediamtx + WHEP)
# ---------------------------------------------------------------------------

async def _webrtc_mode(
    websocket: WebSocket,
    viewer_id: str,
    schedule_id: str,
    room_id: str,
    rtsp_url: str,
):
    """
    WebRTC mode: start recognition pipeline, push only detection metadata.

    Video is delivered via mediamtx → WebRTC (WHEP) — completely separate
    from this WebSocket. This WebSocket only carries ~200-byte detection
    metadata messages at 10 Hz.

    The mobile app calls POST /api/v1/webrtc/{schedule_id}/offer in parallel
    to set up the video peer connection.
    """
    from app.services.recognition_service import recognition_service

    # Start recognition pipeline (RTSP → MediaPipe → FaceNet → FAISS)
    recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
    recog_ok = await recognition_service.start(room_id, recog_url, viewer_id)
    if not recog_ok:
        logger.warning(
            "Recognition service failed to start — WebRTC video will stream "
            "without detection overlays"
        )

    # Send initial connected message (no hls_url — client uses WebRTC for video)
    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "mode": "webrtc",
        "stream_fps": settings.STREAM_FPS,
        "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
    })

    # --- Receive task (handle pings / client disconnect) ---
    stop_event = asyncio.Event()

    async def _receive_loop():
        try:
            while not stop_event.is_set():
                msg = await websocket.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except (WebSocketDisconnect, Exception):
            stop_event.set()

    receive_task = asyncio.create_task(_receive_loop())

    # --- Push detection metadata (identical to _hls_mode loop) ---
    poll_interval = 0.100   # 100ms = 10 Hz
    last_seq = -1
    last_send_time = asyncio.get_event_loop().time()
    heartbeat_interval = 5.0
    stale_count = 0

    try:
        while not stop_event.is_set():
            now = asyncio.get_event_loop().time()
            result = recognition_service.get_latest_detections(room_id)

            if result is not None:
                detections_dicts, update_seq, det_w, det_h = result
                stale_count = 0

                if update_seq != last_seq:
                    last_seq = update_seq

                    if any(d.get("user_id") for d in detections_dicts):
                        det_objects = recognition_service.get_detections_objects(room_id)
                        detections_dicts = _enrich_and_cache(
                            detections_dicts, det_objects, SessionLocal
                        )

                    ts = datetime.now(timezone.utc).isoformat()
                    await websocket.send_json({
                        "type": "detections",
                        "timestamp": ts,
                        "detections": detections_dicts,
                        "detection_width": det_w,
                        "detection_height": det_h,
                    })
                    last_send_time = now

                elif (now - last_send_time) >= heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    last_send_time = now
            else:
                stale_count += 1
                if stale_count >= 100:  # ~10s of no recognition (100 × 100ms)
                    logger.warning(
                        f"Live stream: recognition gone for room {room_id}, "
                        "attempting restart"
                    )
                    recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
                    await recognition_service.start(room_id, recog_url, viewer_id)
                    stale_count = 0

                if (now - last_send_time) >= heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    last_send_time = now

            await asyncio.sleep(poll_interval)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected (WebRTC): viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (WebRTC, viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        try:
            await receive_task
        except (asyncio.CancelledError, Exception):
            pass

        await recognition_service.stop(room_id, viewer_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
```

Also update `live_stream_ws()` to call `_webrtc_mode` first. Find this block (around line 166):

```python
    if settings.USE_HLS_STREAMING:
        await _hls_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
    else:
        await _legacy_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
```

Replace with:

```python
    if settings.USE_WEBRTC_STREAMING:
        await _webrtc_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
    elif settings.USE_HLS_STREAMING:
        await _hls_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
    else:
        await _legacy_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_live_stream_webrtc_mode.py -v
pytest --tb=short -q 2>&1 | tail -10
```

Expected: New tests pass, full suite still green.

**Step 5: Commit**

```bash
git add backend/app/routers/live_stream.py \
        backend/tests/unit/test_live_stream_webrtc_mode.py
git commit -m "feat(webrtc): add _webrtc_mode to live_stream WebSocket — metadata-only, no HLS"
```

---

## Task 6: Install react-native-webrtc (Mobile)

**Files:**
- Modify: `mobile/package.json` (via pnpm)
- Modify: `mobile/android/app/build.gradle` (may be automatic)

**Step 1: Install the package**

```bash
cd mobile
pnpm add react-native-webrtc
```

**Step 2: Verify TypeScript types are available**

```bash
# react-native-webrtc ships its own types — check they're included
grep -r "RTCPeerConnection\|RTCView\|MediaStream" node_modules/react-native-webrtc/src/index.ts | head -5
```

Expected: Lines showing exported types.

**Step 3: Add Android permissions (if not already present)**

Open `mobile/android/app/src/main/AndroidManifest.xml`. Verify these permissions exist (add if missing):

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<!-- WebRTC audio: needed for peer connection even if audio is muted -->
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.CHANGE_NETWORK_STATE" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
```

**Step 4: Run TypeScript check**

```bash
npx tsc --noEmit 2>&1 | grep -v "FaceScanCamera\|config.ts"
```

Expected: No new errors (the 3 pre-existing errors in FaceScanCamera.tsx and config.ts are expected and unrelated).

**Step 5: Commit**

```bash
git add mobile/package.json mobile/pnpm-lock.yaml \
        mobile/android/app/src/main/AndroidManifest.xml
git commit -m "feat(webrtc): install react-native-webrtc, add Android permissions"
```

---

## Task 7: useDetectionWebSocket — expose streamMode

**Files:**
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts`

**Context:** The WebSocket `connected` message in WebRTC mode has `mode: "webrtc"` and no `hls_url`. Currently the hook silently ignores the `mode` field. We need to expose it so `FacultyLiveFeedScreen` knows which video player to use.

**Step 1: Add `streamMode` to the hook**

Open `mobile/src/hooks/useDetectionWebSocket.ts` and make these exact changes:

**Change 1** — Update `ConnectedMessage` interface (line ~35):
```typescript
// Before:
interface ConnectedMessage {
  type: 'connected';
  hls_url: string;
  schedule_id: string;
  room_id: string;
  mode: string;
  stream_fps: number;
  stream_resolution: string;
}

// After:
interface ConnectedMessage {
  type: 'connected';
  hls_url?: string;           // Optional: only present in HLS mode
  schedule_id: string;
  room_id: string;
  mode: 'hls' | 'webrtc' | 'legacy';
  stream_fps: number;
  stream_resolution: string;
}
```

**Change 2** — Add `streamMode` to the return type interface (line ~55):
```typescript
// Add this field to UseDetectionWebSocketReturn:
export interface UseDetectionWebSocketReturn {
  detections: DetectionItem[];
  isConnected: boolean;
  isConnecting: boolean;
  hlsUrl: string | null;
  streamMode: 'hls' | 'webrtc' | 'legacy' | null;   // ← ADD THIS
  studentMap: Map<string, DetectedStudent>;
  connectionError: string | null;
  reconnect: () => void;
  detectionWidth: number;
  detectionHeight: number;
}
```

**Change 3** — Add state variable (after the other useState calls, ~line 87):
```typescript
const [streamMode, setStreamMode] = useState<'hls' | 'webrtc' | 'legacy' | null>(null);
```

**Change 4** — Parse `mode` field in the `connected` message handler (around line 156):
```typescript
// Before:
if (message.type === 'connected') {
  const connMsg = message as ConnectedMessage;
  if (connMsg.hls_url) {
    const baseUrl = config.API_BASE_URL;
    const httpBase = baseUrl.replace(/\/api\/v1$/, '');
    setHlsUrl(`${httpBase}${connMsg.hls_url}`);
  }
}

// After:
if (message.type === 'connected') {
  const connMsg = message as ConnectedMessage;
  setStreamMode(connMsg.mode ?? 'hls');
  if (connMsg.hls_url) {
    const baseUrl = config.API_BASE_URL;
    const httpBase = baseUrl.replace(/\/api\/v1$/, '');
    setHlsUrl(`${httpBase}${connMsg.hls_url}`);
  }
}
```

**Change 5** — Add `streamMode` to the return value (line ~311):
```typescript
return {
  detections,
  isConnected,
  isConnecting,
  hlsUrl,
  streamMode,           // ← ADD THIS
  studentMap,
  connectionError,
  reconnect,
  detectionWidth,
  detectionHeight,
};
```

**Step 2: Run TypeScript check**

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep -v "FaceScanCamera\|config.ts"
```

Expected: No new errors. If TypeScript complains about callers of `useDetectionWebSocket` not destructuring `streamMode`, that's fine — it's a new optional field in the return object. The screen update in Task 9 will destructure it.

**Step 3: Commit**

```bash
git add mobile/src/hooks/useDetectionWebSocket.ts
git commit -m "feat(webrtc): expose streamMode from useDetectionWebSocket hook"
```

---

## Task 8: useWebRTC Hook (Mobile)

**Files:**
- Create: `mobile/src/hooks/useWebRTC.ts`

**Step 1: Create the hook**

```typescript
// mobile/src/hooks/useWebRTC.ts
/**
 * useWebRTC
 *
 * Manages a WebRTC peer connection to the live camera feed.
 * Uses the WHEP protocol via the FastAPI signaling proxy.
 *
 * Flow:
 * 1. GET /api/v1/webrtc/config  → fetch ICE server list (STUN + optional TURN)
 * 2. Create RTCPeerConnection with ICE servers
 * 3. Add recvonly transceivers (video + audio)
 * 4. createOffer() + setLocalDescription()
 * 5. POST /api/v1/webrtc/{scheduleId}/offer  → get SDP answer
 * 6. setRemoteDescription(answer)
 * 7. ICE negotiation → ontrack fires → remoteStream is set → video plays
 *
 * Reconnects automatically with exponential backoff on ICE failure.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  RTCPeerConnection,
  RTCSessionDescription,
  MediaStream,
} from 'react-native-webrtc';
import { config } from '../constants/config';
import { storage } from '../utils/storage';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IceServer {
  urls: string[];
  username?: string;
  credential?: string;
}

export interface UseWebRTCReturn {
  remoteStream: MediaStream | null;
  connectionState: RTCIceConnectionState | 'idle' | 'connecting';
  error: string | null;
  reconnect: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE_RECONNECT_MS = 1_000;   // 1s initial backoff
const MAX_RECONNECT_MS = 30_000;   // 30s max backoff

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWebRTC(scheduleId: string, enabled: boolean): UseWebRTCReturn {
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [connectionState, setConnectionState] = useState<
    RTCIceConnectionState | 'idle' | 'connecting'
  >('idle');
  const [error, setError] = useState<string | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const isMountedRef = useRef(true);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --------------------------------------------------
  // scheduleReconnect — exponential backoff
  // --------------------------------------------------

  const scheduleReconnect = useCallback(() => {
    if (!isMountedRef.current) return;
    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(
      BASE_RECONNECT_MS * Math.pow(2, attempt),
      MAX_RECONNECT_MS,
    );
    reconnectAttemptRef.current = attempt + 1;
    reconnectTimerRef.current = setTimeout(() => {
      if (isMountedRef.current) connect();
    }, delay);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------------------------------------------------
  // connect — full WebRTC handshake
  // --------------------------------------------------

  const connect = useCallback(async () => {
    if (!isMountedRef.current || !enabled) return;

    // Tear down any previous peer connection
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    setRemoteStream(null);
    setError(null);
    setConnectionState('connecting');

    try {
      // Step 1: Get ICE servers from backend
      const token = await storage.getAccessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };

      const configResp = await fetch(`${config.API_BASE_URL}/webrtc/config`, {
        headers,
      });
      if (!configResp.ok) {
        throw new Error(`Failed to fetch ICE config (${configResp.status})`);
      }
      const configData = await configResp.json();
      const iceServers: IceServer[] = configData?.data?.ice_servers ?? [
        { urls: ['stun:stun.l.google.com:19302'] },
      ];

      // Step 2: Create peer connection
      const pc = new RTCPeerConnection({ iceServers } as any);
      pcRef.current = pc;

      // Step 3: Add receive-only transceivers (video + audio)
      pc.addTransceiver('video', { direction: 'recvonly' });
      pc.addTransceiver('audio', { direction: 'recvonly' });

      // Step 4a: Handle incoming video track
      pc.ontrack = (event: any) => {
        if (event.streams?.[0] && isMountedRef.current) {
          setRemoteStream(event.streams[0]);
        }
      };

      // Step 4b: Track ICE connection state
      pc.oniceconnectionstatechange = () => {
        if (!isMountedRef.current) return;
        const state = pc.iceConnectionState as RTCIceConnectionState;
        setConnectionState(state);

        if (state === 'connected' || state === 'completed') {
          reconnectAttemptRef.current = 0;
          setError(null);
        }

        if (state === 'failed' || state === 'disconnected') {
          scheduleReconnect();
        }
      };

      // Step 5: Create offer and set local description
      const offer = await pc.createOffer({} as any);
      await pc.setLocalDescription(offer);

      // Step 6: POST offer to FastAPI signaling proxy
      const offerResp = await fetch(
        `${config.API_BASE_URL}/webrtc/${scheduleId}/offer`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
        },
      );

      if (!offerResp.ok) {
        const errBody = await offerResp.json().catch(() => ({}));
        throw new Error(
          errBody?.detail ?? `Offer rejected (${offerResp.status})`,
        );
      }

      const offerData = await offerResp.json();
      const { sdp, type } = offerData.data;

      // Step 7: Set remote description (answer from mediamtx)
      await pc.setRemoteDescription(new RTCSessionDescription({ sdp, type }));

      // ICE negotiation now proceeds automatically.
      // oniceconnectionstatechange will fire when video flows.

    } catch (err: unknown) {
      if (!isMountedRef.current) return;
      const message =
        err instanceof Error ? err.message : 'WebRTC connection failed';
      setError(message);
      setConnectionState('failed' as RTCIceConnectionState);
      scheduleReconnect();
    }
  }, [scheduleId, enabled, scheduleReconnect]);

  // --------------------------------------------------
  // Mount / unmount
  // --------------------------------------------------

  useEffect(() => {
    isMountedRef.current = true;

    if (enabled) {
      connect();
    }

    return () => {
      isMountedRef.current = false;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
    };
  }, [connect, enabled]);

  // --------------------------------------------------
  // Manual reconnect (resets backoff counter)
  // --------------------------------------------------

  const reconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptRef.current = 0;
    connect();
  }, [connect]);

  return { remoteStream, connectionState, error, reconnect };
}
```

**Step 2: Run TypeScript check**

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep -v "FaceScanCamera\|config.ts"
```

Expected: No new errors.

**Step 3: Commit**

```bash
git add mobile/src/hooks/useWebRTC.ts
git commit -m "feat(webrtc): add useWebRTC hook — WHEP signaling, ICE config, exponential backoff"
```

---

## Task 9: FacultyLiveFeedScreen — WebRTC Video

**Files:**
- Modify: `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx`

**Context:** Currently the screen uses `useVideoPlayer`/`VideoView` (expo-video). We keep HLS as a fallback but add conditional rendering for WebRTC mode. Both hooks are always called (React hooks rule — no conditional hook calls); only the relevant one is active.

**Step 1: Update imports**

At the top of `FacultyLiveFeedScreen.tsx`, update the imports:

```typescript
// Before:
import { useVideoPlayer, VideoView } from 'expo-video';

// After:
import { useVideoPlayer, VideoView } from 'expo-video';
import { RTCView } from 'react-native-webrtc';
```

Also update the `useDetectionWebSocket` import to destructure `streamMode`:

```typescript
// The import itself doesn't change, but we destructure streamMode below
import { useDetectionWebSocket } from '../../hooks/useDetectionWebSocket';
import type { DetectedStudent } from '../../hooks/useDetectionWebSocket';
import { useWebRTC } from '../../hooks/useWebRTC';
```

**Step 2: Update the component body**

Find the section where `useDetectionWebSocket` is called (line ~148):

```typescript
// Before:
const {
  detections,
  isConnected,
  isConnecting,
  hlsUrl,
  studentMap,
  connectionError,
  reconnect,
  detectionWidth,
  detectionHeight,
} = useDetectionWebSocket(scheduleId);

// Video player — source updates when hlsUrl arrives.
const player = useVideoPlayer(hlsUrl, (p) => {
  p.loop = false;
  if (hlsUrl) {
    p.play();
  }
});
```

Replace with:

```typescript
const {
  detections,
  isConnected,
  isConnecting,
  hlsUrl,
  streamMode,
  studentMap,
  connectionError,
  reconnect,
  detectionWidth,
  detectionHeight,
} = useDetectionWebSocket(scheduleId);

// WebRTC video (enabled only in webrtc mode)
const {
  remoteStream,
  connectionState: rtcConnectionState,
  reconnect: rtcReconnect,
} = useWebRTC(scheduleId, streamMode === 'webrtc');

// HLS video player (enabled only in hls/legacy mode)
// When streamMode is 'webrtc', pass null to avoid starting an HLS connection.
const player = useVideoPlayer(
  streamMode === 'hls' || streamMode === 'legacy' ? hlsUrl : null,
  (p) => {
    p.loop = false;
    if (hlsUrl && (streamMode === 'hls' || streamMode === 'legacy')) {
      p.play();
    }
  },
);

// Combined reconnect: resets both WS and WebRTC connections
const handleReconnect = useCallback(() => {
  reconnect();
  if (streamMode === 'webrtc') rtcReconnect();
}, [reconnect, rtcReconnect, streamMode]);
```

**Step 3: Update the loading state check**

Find (line ~287):
```typescript
if (isConnecting && !hlsUrl) {
```

Replace with:
```typescript
const isVideoReady =
  (streamMode === 'webrtc' && remoteStream !== null) ||
  ((streamMode === 'hls' || streamMode === 'legacy') && hlsUrl !== null);

if (isConnecting && !isVideoReady) {
```

**Step 4: Update the error state reconnect button**

In the error state block (around line 270), change `onPress={reconnect}` to `onPress={handleReconnect}`.

**Step 5: Update the video rendering block**

Find the camera feed section (around line 362):

```typescript
{/* Camera feed: native HLS video + detection overlay */}
<View style={styles.feedContainer} onLayout={handleVideoLayout}>
  {hlsUrl ? (
    <>
      <VideoView
        player={player}
        style={styles.video}
        contentFit="contain"
        nativeControls={false}
      />
      <DetectionOverlay ... />
    </>
  ) : (
    <View style={styles.noFeedPlaceholder}>
      ...
    </View>
  )}
</View>
```

Replace with:

```typescript
{/* Camera feed: WebRTC or HLS video + detection overlay */}
<View style={styles.feedContainer} onLayout={handleVideoLayout}>
  {streamMode === 'webrtc' && remoteStream ? (
    <>
      <RTCView
        streamURL={remoteStream.toURL()}
        style={styles.video}
        objectFit="cover"
        mirror={false}
        zOrder={0}
      />
      <DetectionOverlay
        detections={detections}
        videoWidth={detectionWidth}
        videoHeight={detectionHeight}
        containerWidth={containerLayout.width}
        containerHeight={containerLayout.height}
      />
    </>
  ) : (streamMode === 'hls' || streamMode === 'legacy') && hlsUrl ? (
    <>
      <VideoView
        player={player}
        style={styles.video}
        contentFit="contain"
        nativeControls={false}
      />
      <DetectionOverlay
        detections={detections}
        videoWidth={detectionWidth}
        videoHeight={detectionHeight}
        containerWidth={containerLayout.width}
        containerHeight={containerLayout.height}
      />
    </>
  ) : (
    <View style={styles.noFeedPlaceholder}>
      <Video size={48} color={theme.colors.text.disabled} />
      <Text
        variant="bodySmall"
        color={theme.colors.text.tertiary}
        align="center"
        style={styles.noFeedText}
      >
        {rtcConnectionState === 'failed'
          ? 'WebRTC connection failed — tap retry'
          : 'Connecting to camera...'}
      </Text>
    </View>
  )}
</View>
```

**Step 6: Run TypeScript check**

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep -v "FaceScanCamera\|config.ts"
```

Expected: No new errors.

**Step 7: Commit**

```bash
git add mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx
git commit -m "feat(webrtc): replace VideoView with RTCView in FacultyLiveFeedScreen"
```

---

## Task 10: Final Integration Check

**Step 1: Run full backend test suite**

```bash
cd backend && source venv/bin/activate
pytest --tb=short -q 2>&1 | tail -20
```

Expected: All previous 524 tests pass + new tests (Tasks 1, 3, 4, 5) = ~546 passed, 1 skipped.

**Step 2: Run TypeScript type-check on entire mobile project**

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep -v "FaceScanCamera\|config.ts"
```

Expected: No new errors (3 pre-existing unrelated errors are acceptable).

**Step 3: Verify config values**

```bash
cd backend && source venv/bin/activate && python -c "
from app.config import settings
assert settings.USE_WEBRTC_STREAMING is True
print('✓ USE_WEBRTC_STREAMING =', settings.USE_WEBRTC_STREAMING)
assert settings.MEDIAMTX_API_URL == 'http://localhost:9997'
print('✓ MEDIAMTX_API_URL =', settings.MEDIAMTX_API_URL)
assert settings.MEDIAMTX_WEBRTC_URL == 'http://localhost:8889'
print('✓ MEDIAMTX_WEBRTC_URL =', settings.MEDIAMTX_WEBRTC_URL)
assert 'stun.l.google.com' in settings.WEBRTC_STUN_URLS
print('✓ WEBRTC_STUN_URLS =', settings.WEBRTC_STUN_URLS)
print()
print('All WebRTC config values verified ✓')
"
```

**Step 4: Manual end-to-end smoke test**

In two separate terminals:

```bash
# Terminal 1 — mediamtx
cd backend && ./bin/mediamtx mediamtx.yml

# Terminal 2 — FastAPI
cd backend && source venv/bin/activate && python run.py
```

Verify:
- `GET http://localhost:8000/api/v1/webrtc/config` → returns ICE servers
- `GET ws://localhost:8000/api/v1/stream/{schedule_id}` → connected message has `mode: "webrtc"` (no `hls_url`)
- With a real RTSP camera: `POST /api/v1/webrtc/{schedule_id}/offer` with a valid SDP → returns SDP answer

**Step 5: Final commit for docs**

```bash
cd /path/to/iams
git add docs/plans/2026-03-01-webrtc-live-feed-plan.md
git commit -m "docs: add WebRTC live feed implementation plan"
```

---

## Production Deployment Notes

When moving from localhost to a real server:

1. **mediamtx public IP** — In `mediamtx.yml`, add your server's public IP:
   ```yaml
   webrtcAdditionalHosts: [YOUR_PUBLIC_IP]
   ```

2. **Firewall** — Open UDP port 8888 (ICE candidates) on the server firewall.

3. **TURN for cellular clients** — Set in `.env`:
   ```
   WEBRTC_TURN_URL=turn:your-coturn-server:3478
   WEBRTC_TURN_USERNAME=iams
   WEBRTC_TURN_CREDENTIAL=your-secret
   ```

4. **nginx reverse proxy** — mediamtx's REST API (port 9997) must NOT be exposed. Only FastAPI (:8000) should be behind nginx. The WHEP endpoint (:8889) is internal — FastAPI proxies it.

5. **Mobile `.env`** — Set the production API URL:
   ```
   EXPO_PUBLIC_API_BASE_URL=https://api.your-school.edu/api/v1
   ```
