"""
Tests for WebSocket router and ConnectionManager.

Covers:
- GET /ws/status endpoint (connection count)
- ConnectionManager unit tests (connect, disconnect, send, broadcast, schedule subscriptions)
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.routers.websocket import ConnectionManager

API = settings.API_PREFIX


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_mock_ws():
    """Create a mock WebSocket with async accept and send_json."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# HTTP status endpoint
# ---------------------------------------------------------------------------

class TestWebSocketStatus:
    """Tests for the GET /ws/status health-check endpoint."""

    def test_ws_status_returns_connection_count(self, client):
        """GET /ws/status should return active connection count and running status."""
        response = client.get(f"{API}/ws/status")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "running"
        assert isinstance(body["data"]["active_connections"], int)
        assert body["data"]["active_connections"] >= 0


# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------

class TestConnectionManager:
    """Unit tests for the ConnectionManager class.

    Each test creates its own ConnectionManager instance so there is no
    shared state between tests.
    """

    def test_connect_and_disconnect(self):
        """Connecting a websocket increments the count; disconnecting decrements it."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()

            await manager.connect("user1", mock_ws)
            mock_ws.accept.assert_awaited_once()
            assert manager.get_connection_count() == 1

            manager.disconnect("user1")
            assert manager.get_connection_count() == 0

        asyncio.run(_test())

    def test_send_personal_to_connected_user(self):
        """Sending a personal message to a connected user calls send_json."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()

            await manager.connect("user1", mock_ws)

            message = {"type": "notification", "text": "hello"}
            await manager.send_personal("user1", message)

            mock_ws.send_json.assert_awaited_once_with(message)

        asyncio.run(_test())

    def test_send_personal_to_unknown_user(self):
        """Sending a personal message to an unknown user should not raise."""

        async def _test():
            manager = ConnectionManager()
            # Should complete without error even though no one is connected
            await manager.send_personal("nonexistent_user", {"msg": "hi"})

        asyncio.run(_test())

    def test_register_for_schedule(self):
        """Registering a user for a schedule increases the subscriber count."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()
            await manager.connect("user1", mock_ws)

            manager.register_for_schedule("user1", "schedule_abc")
            assert manager.get_schedule_subscriber_count("schedule_abc") == 1

        asyncio.run(_test())

    def test_unregister_from_schedule(self):
        """Unregistering removes the user; empty schedule sets are cleaned up."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()
            await manager.connect("user1", mock_ws)

            manager.register_for_schedule("user1", "schedule_abc")
            assert manager.get_schedule_subscriber_count("schedule_abc") == 1

            manager.unregister_from_schedule("user1", "schedule_abc")
            assert manager.get_schedule_subscriber_count("schedule_abc") == 0

        asyncio.run(_test())

    def test_broadcast_to_schedule(self):
        """Broadcasting to a schedule sends the message to all subscribers."""

        async def _test():
            manager = ConnectionManager()
            ws1 = _make_mock_ws()
            ws2 = _make_mock_ws()

            await manager.connect("user1", ws1)
            await manager.connect("user2", ws2)

            manager.register_for_schedule("user1", "schedule_abc")
            manager.register_for_schedule("user2", "schedule_abc")

            message = {"type": "attendance_update", "data": "payload"}
            await manager.broadcast_to_schedule("schedule_abc", message)

            ws1.send_json.assert_awaited_once_with(message)
            ws2.send_json.assert_awaited_once_with(message)

        asyncio.run(_test())

    def test_disconnect_cleans_schedule_subs(self):
        """Disconnecting a user removes them from all schedule subscriptions."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()

            await manager.connect("user1", mock_ws)
            manager.register_for_schedule("user1", "schedule_abc")
            manager.register_for_schedule("user1", "schedule_xyz")

            assert manager.get_schedule_subscriber_count("schedule_abc") == 1
            assert manager.get_schedule_subscriber_count("schedule_xyz") == 1

            manager.disconnect("user1")

            assert manager.get_schedule_subscriber_count("schedule_abc") == 0
            assert manager.get_schedule_subscriber_count("schedule_xyz") == 0
            assert manager.get_connection_count() == 0

        asyncio.run(_test())
