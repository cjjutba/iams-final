"""
Session 05 — WebSocket protocol and health/time endpoint tests.

Verifies the additive protocol fields on `frame_update`:
  - `server_time_ms` is a UTC epoch millisecond int within ±5s of now.
  - `frame_sequence` strictly increases within a session.

Also verifies the public `GET /api/v1/health/time` endpoint shape.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.realtime_pipeline import SessionPipeline
from app.services.realtime_tracker import TrackFrame


API = settings.API_PREFIX


def _make_track_frame(ts: float | None = None) -> TrackFrame:
    """Build an empty TrackFrame for a broadcast test."""
    return TrackFrame(
        tracks=[],
        fps=10.0,
        processing_ms=5.0,
        timestamp=ts if ts is not None else time.monotonic(),
    )


def _make_pipeline() -> SessionPipeline:
    """Construct a SessionPipeline without starting its loop."""
    return SessionPipeline(
        schedule_id="11111111-1111-1111-1111-111111111111",
        grabber=None,
        db_factory=lambda: None,
    )


# ---------------------------------------------------------------------------
# frame_update payload additions
# ---------------------------------------------------------------------------


class TestFrameUpdatePayload:
    """The frame_update broadcast must carry server_time_ms + frame_sequence."""

    def test_frame_update_contains_server_time_ms(self):
        """server_time_ms must be a UTC epoch-ms int within ±5s of now."""

        async def _run():
            pipeline = _make_pipeline()
            mock_broadcast = AsyncMock()

            with patch(
                "app.routers.websocket.ws_manager.broadcast_attendance",
                new=mock_broadcast,
            ):
                before = int(time.time() * 1000)
                await pipeline._broadcast_frame_update(_make_track_frame())
                after = int(time.time() * 1000)

            assert mock_broadcast.await_count == 1
            _schedule_id, payload = mock_broadcast.await_args.args
            assert payload["type"] == "frame_update"
            assert "server_time_ms" in payload
            assert isinstance(payload["server_time_ms"], int)
            # Monotonic bounds — no ±5s fudge needed; tighter is fine.
            assert before <= payload["server_time_ms"] <= after
            # Sanity — same order of magnitude as wall-clock epoch ms.
            assert abs(payload["server_time_ms"] - int(time.time() * 1000)) < 5000

        asyncio.run(_run())

    def test_frame_update_contains_frame_sequence(self):
        """frame_sequence is an int starting at 1 on the first broadcast."""

        async def _run():
            pipeline = _make_pipeline()
            assert pipeline._frame_sequence == 0

            mock_broadcast = AsyncMock()
            with patch(
                "app.routers.websocket.ws_manager.broadcast_attendance",
                new=mock_broadcast,
            ):
                await pipeline._broadcast_frame_update(_make_track_frame())

            _sid, payload = mock_broadcast.await_args.args
            assert payload["frame_sequence"] == 1

        asyncio.run(_run())

    def test_frame_sequence_monotonic(self):
        """frame_sequence must strictly increase across consecutive broadcasts."""

        async def _run():
            pipeline = _make_pipeline()
            mock_broadcast = AsyncMock()

            with patch(
                "app.routers.websocket.ws_manager.broadcast_attendance",
                new=mock_broadcast,
            ):
                for _ in range(5):
                    await pipeline._broadcast_frame_update(_make_track_frame())

            sequences = [call.args[1]["frame_sequence"] for call in mock_broadcast.await_args_list]
            assert sequences == [1, 2, 3, 4, 5]
            assert all(b > a for a, b in zip(sequences, sequences[1:]))

        asyncio.run(_run())

    def test_existing_payload_keys_preserved(self):
        """Legacy keys (timestamp, frame_size, tracks, fps, processing_ms) stay present."""

        async def _run():
            pipeline = _make_pipeline()
            mock_broadcast = AsyncMock()
            frame = _make_track_frame(ts=123.456)

            with patch(
                "app.routers.websocket.ws_manager.broadcast_attendance",
                new=mock_broadcast,
            ):
                await pipeline._broadcast_frame_update(frame)

            _sid, payload = mock_broadcast.await_args.args
            for key in ("type", "timestamp", "frame_size", "tracks", "fps", "processing_ms"):
                assert key in payload, f"missing legacy key {key!r}"
            assert payload["timestamp"] == 123.456
            assert payload["tracks"] == []

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# GET /api/v1/health/time
# ---------------------------------------------------------------------------


class TestHealthTimeEndpoint:
    """GET /api/v1/health/time returns {'server_time_ms': <epoch-ms>}."""

    def test_health_time_returns_200(self, client):
        response = client.get(f"{API}/health/time")
        assert response.status_code == 200

    def test_health_time_shape(self, client):
        response = client.get(f"{API}/health/time")
        data = response.json()
        assert set(data.keys()) == {"server_time_ms"}
        assert isinstance(data["server_time_ms"], int)

    def test_health_time_within_skew(self, client):
        """Returned epoch ms must be within ±5s of the local clock."""
        response = client.get(f"{API}/health/time")
        data = response.json()
        assert abs(data["server_time_ms"] - int(time.time() * 1000)) < 5000
