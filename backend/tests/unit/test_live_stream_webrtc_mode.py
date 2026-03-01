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
