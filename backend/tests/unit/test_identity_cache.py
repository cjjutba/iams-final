"""
Unit Tests for IdentityCache

Tests the Redis-backed identity cache that bridges the Attendance Engine
(writes identities after each scan) and the Live Feed Pipeline (reads
them to label tracked faces without running ArcFace).

Uses AsyncMock to simulate redis.asyncio.Redis — no real Redis required.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.identity_cache import IdentityCache, DEFAULT_TTL


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Provide an AsyncMock that mimics redis.asyncio.Redis."""
    r = AsyncMock()
    # hgetall returns empty dict by default (cache miss)
    r.hgetall = AsyncMock(return_value={})
    r.hset = AsyncMock()
    r.expire = AsyncMock()
    r.delete = AsyncMock()
    return r


@pytest.fixture
def cache(mock_redis):
    return IdentityCache(mock_redis)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

ROOM_ID = "room-101"
SESSION_ID = "sess-abc-123"

IDENTITIES = [
    {
        "user_id": "u1",
        "name": "Juan Dela Cruz",
        "confidence": 0.92,
        "bbox": [100, 200, 150, 250],
        "last_seen_ts": 1710700000.0,
    },
    {
        "user_id": "u2",
        "name": "Maria Santos",
        "confidence": 0.88,
        "bbox": [300, 100, 380, 200],
        "last_seen_ts": 1710700001.0,
    },
]

SCAN_META = {
    "scan_number": 3,
    "scanned_at": "2026-03-17T10:00:00",
    "total_faces": 5,
    "matched_faces": 2,
}


# ---------------------------------------------------------------------------
# write_identities
# ---------------------------------------------------------------------------

class TestWriteIdentities:
    @pytest.mark.asyncio
    async def test_stores_data_and_sets_ttl(self, cache, mock_redis):
        await cache.write_identities(ROOM_ID, SESSION_ID, IDENTITIES)

        expected_key = f"attendance:{ROOM_ID}:{SESSION_ID}:identities"

        # hset called once with a mapping
        mock_redis.hset.assert_awaited_once()
        call_args = mock_redis.hset.call_args
        assert call_args.kwargs["name"] == expected_key

        mapping = call_args.kwargs["mapping"]
        assert "u1" in mapping
        assert "u2" in mapping

        # Values are JSON strings
        parsed_u1 = json.loads(mapping["u1"])
        assert parsed_u1["name"] == "Juan Dela Cruz"
        assert parsed_u1["confidence"] == 0.92

        # TTL is set
        mock_redis.expire.assert_awaited_once_with(expected_key, DEFAULT_TTL)

    @pytest.mark.asyncio
    async def test_custom_ttl(self, cache, mock_redis):
        custom_ttl = 600
        await cache.write_identities(ROOM_ID, SESSION_ID, IDENTITIES, ttl=custom_ttl)

        expected_key = f"attendance:{ROOM_ID}:{SESSION_ID}:identities"
        mock_redis.expire.assert_awaited_once_with(expected_key, custom_ttl)

    @pytest.mark.asyncio
    async def test_empty_identities_skips_write(self, cache, mock_redis):
        await cache.write_identities(ROOM_ID, SESSION_ID, [])

        mock_redis.hset.assert_not_awaited()


# ---------------------------------------------------------------------------
# read_identities
# ---------------------------------------------------------------------------

class TestReadIdentities:
    @pytest.mark.asyncio
    async def test_returns_parsed_dicts(self, cache, mock_redis):
        # Simulate Redis returning bytes keys and values
        mock_redis.hgetall.return_value = {
            b"u1": json.dumps({
                "name": "Juan Dela Cruz",
                "confidence": 0.92,
                "bbox": [100, 200, 150, 250],
                "last_seen_ts": 1710700000.0,
            }).encode(),
            b"u2": json.dumps({
                "name": "Maria Santos",
                "confidence": 0.88,
                "bbox": [300, 100, 380, 200],
                "last_seen_ts": 1710700001.0,
            }).encode(),
        }

        result = await cache.read_identities(ROOM_ID, SESSION_ID)

        expected_key = f"attendance:{ROOM_ID}:{SESSION_ID}:identities"
        mock_redis.hgetall.assert_awaited_once_with(expected_key)

        assert isinstance(result, dict)
        assert len(result) == 2
        assert result["u1"]["name"] == "Juan Dela Cruz"
        assert result["u2"]["confidence"] == 0.88

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_cache_miss(self, cache, mock_redis):
        mock_redis.hgetall.return_value = {}

        result = await cache.read_identities(ROOM_ID, SESSION_ID)

        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_str_keys(self, cache, mock_redis):
        """Some Redis client configs return str keys instead of bytes."""
        mock_redis.hgetall.return_value = {
            "u1": json.dumps({"name": "Test", "confidence": 0.9}).encode(),
        }

        result = await cache.read_identities(ROOM_ID, SESSION_ID)
        assert "u1" in result


# ---------------------------------------------------------------------------
# write_scan_meta / read_scan_meta
# ---------------------------------------------------------------------------

class TestScanMeta:
    @pytest.mark.asyncio
    async def test_write_scan_meta_stores_metadata(self, cache, mock_redis):
        await cache.write_scan_meta(ROOM_ID, SESSION_ID, SCAN_META)

        expected_key = f"attendance:{ROOM_ID}:{SESSION_ID}:scan_meta"

        mock_redis.hset.assert_awaited_once()
        call_args = mock_redis.hset.call_args
        assert call_args.kwargs["name"] == expected_key

        mapping = call_args.kwargs["mapping"]
        # Each meta field becomes a hash field with JSON-encoded value
        for field_key in SCAN_META:
            assert field_key in mapping

        mock_redis.expire.assert_awaited_once_with(expected_key, DEFAULT_TTL)

    @pytest.mark.asyncio
    async def test_read_scan_meta_returns_dict(self, cache, mock_redis):
        mock_redis.hgetall.return_value = {
            b"scan_number": b"3",
            b"scanned_at": b'"2026-03-17T10:00:00"',
            b"total_faces": b"5",
            b"matched_faces": b"2",
        }

        result = await cache.read_scan_meta(ROOM_ID, SESSION_ID)

        expected_key = f"attendance:{ROOM_ID}:{SESSION_ID}:scan_meta"
        mock_redis.hgetall.assert_awaited_once_with(expected_key)

        assert result is not None
        assert result["scan_number"] == 3
        assert result["total_faces"] == 5

    @pytest.mark.asyncio
    async def test_read_scan_meta_returns_none_on_miss(self, cache, mock_redis):
        mock_redis.hgetall.return_value = {}

        result = await cache.read_scan_meta(ROOM_ID, SESSION_ID)
        assert result is None


# ---------------------------------------------------------------------------
# clear_session
# ---------------------------------------------------------------------------

class TestClearSession:
    @pytest.mark.asyncio
    async def test_deletes_both_keys(self, cache, mock_redis):
        await cache.clear_session(ROOM_ID, SESSION_ID)

        identity_key = f"attendance:{ROOM_ID}:{SESSION_ID}:identities"
        meta_key = f"attendance:{ROOM_ID}:{SESSION_ID}:scan_meta"

        mock_redis.delete.assert_awaited_once_with(identity_key, meta_key)
