"""
Tests for WebSocket ConnectionManager.

Covers the current API: add/remove attendance and alert clients, broadcasting.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.routers.websocket import ConnectionManager


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
# ConnectionManager unit tests
# ---------------------------------------------------------------------------

class TestConnectionManager:
    """Unit tests for the ConnectionManager class."""

    def test_add_and_remove_attendance_client(self):
        """Adding a client registers it; removing discards it."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()

            await manager.add_attendance_client("schedule-1", mock_ws)
            mock_ws.accept.assert_awaited_once()
            assert mock_ws in manager._attendance_clients["schedule-1"]

            manager.remove_attendance_client("schedule-1", mock_ws)
            assert mock_ws not in manager._attendance_clients["schedule-1"]

        asyncio.run(_test())

    def test_add_and_remove_alert_client(self):
        """Adding an alert client registers it; removing discards it."""

        async def _test():
            manager = ConnectionManager()
            mock_ws = _make_mock_ws()

            await manager.add_alert_client("user-1", mock_ws)
            mock_ws.accept.assert_awaited_once()
            assert mock_ws in manager._alert_clients["user-1"]

            manager.remove_alert_client("user-1", mock_ws)
            assert mock_ws not in manager._alert_clients["user-1"]

        asyncio.run(_test())

    def test_broadcast_attendance_sends_to_all(self):
        """Broadcasting sends data to all connected clients for a schedule."""

        async def _test():
            manager = ConnectionManager()
            ws1 = _make_mock_ws()
            ws2 = _make_mock_ws()

            await manager.add_attendance_client("schedule-1", ws1)
            await manager.add_attendance_client("schedule-1", ws2)

            message = {"type": "scan_result", "data": "test"}
            await manager.broadcast_attendance("schedule-1", message)

            ws1.send_json.assert_awaited_once_with(message)
            ws2.send_json.assert_awaited_once_with(message)

        asyncio.run(_test())

    def test_broadcast_removes_dead_clients(self):
        """Dead clients (raise on send) are removed from the set."""

        async def _test():
            manager = ConnectionManager()
            good_ws = _make_mock_ws()
            dead_ws = _make_mock_ws()
            dead_ws.send_json.side_effect = Exception("connection closed")

            await manager.add_attendance_client("schedule-1", good_ws)
            await manager.add_attendance_client("schedule-1", dead_ws)

            await manager.broadcast_attendance("schedule-1", {"test": True})

            # Dead client should be removed
            assert dead_ws not in manager._attendance_clients["schedule-1"]
            # Good client should remain
            assert good_ws in manager._attendance_clients["schedule-1"]

        asyncio.run(_test())
