"""
Identity Cache — Redis bridge between Attendance Engine and Live Feed Pipeline.

The Attendance Engine WRITES identified faces after each presence scan.
The Live Feed Pipeline READS them to label tracked faces in the composited
video stream without running ArcFace inference on every frame.

Keys are session-scoped to prevent cross-class identity leakage:
  attendance:{room_id}:{session_id}:identities   — hash of user_id → JSON
  attendance:{room_id}:{session_id}:scan_meta     — hash of metadata fields

Default TTL: 3 hours + 5 min buffer = 11100 seconds (covers the longest
possible class duration plus a safety margin).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 3 hours + 5 min buffer
DEFAULT_TTL: int = 11_100


class IdentityCache:
    """Async Redis-backed cache for per-session face identities."""

    def __init__(self, redis_client) -> None:
        """
        Args:
            redis_client: An ``redis.asyncio.Redis`` instance (or compatible
                async mock).  Expected to have ``decode_responses=False``
                so values come back as ``bytes``.
        """
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identity_key(room_id: str, session_id: str) -> str:
        return f"attendance:{room_id}:{session_id}:identities"

    @staticmethod
    def _meta_key(room_id: str, session_id: str) -> str:
        return f"attendance:{room_id}:{session_id}:scan_meta"

    # ------------------------------------------------------------------
    # Identity read / write
    # ------------------------------------------------------------------

    async def write_identities(
        self,
        room_id: str,
        session_id: str,
        identities: list[dict[str, Any]],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Write a list of identity dicts to a Redis hash.

        Each entry uses ``user_id`` as the hash field and a JSON-encoded
        dict (name, confidence, bbox, last_seen_ts) as the value.

        Args:
            room_id: Room identifier.
            session_id: Session identifier.
            identities: List of identity dicts, each **must** contain a
                ``user_id`` key.  Remaining fields are stored as JSON.
            ttl: Time-to-live in seconds (default ``DEFAULT_TTL``).
        """
        if not identities:
            return

        key = self._identity_key(room_id, session_id)

        mapping: dict[str, str] = {}
        for identity in identities:
            user_id = identity["user_id"]
            # Store everything except user_id (it's the hash field already)
            value = {k: v for k, v in identity.items() if k != "user_id"}
            mapping[user_id] = json.dumps(value)

        await self._redis.hset(name=key, mapping=mapping)
        await self._redis.expire(key, ttl)

        logger.debug(
            "Wrote %d identities to %s (ttl=%ds)", len(mapping), key, ttl,
        )

    async def read_identities(
        self, room_id: str, session_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Read all identities for a session.

        Returns:
            Mapping of ``user_id`` to parsed identity dict.
            Empty dict on cache miss.
        """
        key = self._identity_key(room_id, session_id)
        raw: dict = await self._redis.hgetall(key)

        if not raw:
            return {}

        result: dict[str, dict[str, Any]] = {}
        for field, value in raw.items():
            # Keys/values may be bytes when decode_responses=False
            uid = field.decode() if isinstance(field, bytes) else field
            val = value.decode() if isinstance(value, bytes) else value
            result[uid] = json.loads(val)

        return result

    # ------------------------------------------------------------------
    # Scan metadata read / write
    # ------------------------------------------------------------------

    async def write_scan_meta(
        self,
        room_id: str,
        session_id: str,
        meta: dict[str, Any],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Write scan metadata to a Redis hash.

        Each key in *meta* becomes a hash field with a JSON-encoded value.

        Args:
            room_id: Room identifier.
            session_id: Session identifier.
            meta: Metadata dict (e.g. scan_number, scanned_at, etc.).
            ttl: Time-to-live in seconds.
        """
        key = self._meta_key(room_id, session_id)

        mapping: dict[str, str] = {
            k: json.dumps(v) for k, v in meta.items()
        }

        await self._redis.hset(name=key, mapping=mapping)
        await self._redis.expire(key, ttl)

        logger.debug("Wrote scan meta to %s (ttl=%ds)", key, ttl)

    async def read_scan_meta(
        self, room_id: str, session_id: str,
    ) -> dict[str, Any] | None:
        """Read scan metadata for a session.

        Returns:
            Parsed metadata dict, or ``None`` on cache miss.
        """
        key = self._meta_key(room_id, session_id)
        raw: dict = await self._redis.hgetall(key)

        if not raw:
            return None

        result: dict[str, Any] = {}
        for field, value in raw.items():
            k = field.decode() if isinstance(field, bytes) else field
            v = value.decode() if isinstance(value, bytes) else value
            result[k] = json.loads(v)

        return result

    # ------------------------------------------------------------------
    # Session cleanup
    # ------------------------------------------------------------------

    async def clear_session(self, room_id: str, session_id: str) -> None:
        """Delete both identity and metadata keys for a session.

        Called when a session ends to free Redis memory immediately
        rather than waiting for TTL expiry.
        """
        identity_key = self._identity_key(room_id, session_id)
        meta_key = self._meta_key(room_id, session_id)

        await self._redis.delete(identity_key, meta_key)

        logger.debug(
            "Cleared session cache: room=%s session=%s", room_id, session_id,
        )
