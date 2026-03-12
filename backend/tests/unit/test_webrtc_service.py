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

    def test_empty_stun_urls_produces_no_stun_entry(self, mock_settings):
        mock_settings.WEBRTC_STUN_URLS = ""
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()
        servers = svc.get_ice_servers()
        assert all(len(s.get("urls", [])) > 0 for s in servers)

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
            mock_client.patch.assert_called_once_with(
                "http://localhost:9997/v3/config/paths/patch/room-1",
                json={"source": "rtsp://cam/stream", "sourceOnDemand": True},
            )

    @pytest.mark.asyncio
    async def test_returns_false_on_connect_error(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            result = await svc.ensure_path("room-1", "rtsp://cam/stream")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_unexpected_exception(self, mock_settings):
        from app.services.webrtc_service import WebRTCService
        svc = WebRTCService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_client_cls.return_value = mock_client

            result = await svc.ensure_path("room-1", "rtsp://cam/stream")
            assert result is False


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
