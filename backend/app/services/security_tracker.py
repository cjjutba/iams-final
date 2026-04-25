"""Security event tracker.

Redis-backed counters for security-sensitive events that need rate-limiting
or burst detection (failed-login bursts, etc). All functions are safe to
call when Redis is unavailable — they degrade to no-ops + log warnings.

The Redis client used (``app.redis_client.get_redis``) is async — this
module mirrors that, so all entry points are coroutines. Callers that
run inside a sync context can either convert to ``async def`` (preferred
in FastAPI route handlers) or schedule via ``asyncio.run_coroutine_threadsafe``.

Identifiers are SHA-256 hashed before being used as Redis keys to avoid
storing raw email/student-id values in the cache.
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

_FAILED_LOGIN_KEY_PREFIX = "auth:fail:"
_FAILED_LOGIN_TTL_SECONDS = 300  # 5 minutes
_BURST_THRESHOLD = 3


def _hash_identifier(identifier: str) -> str:
    """SHA-256 first 16 bytes of normalized identifier — avoids storing raw PII."""
    normalized = (identifier or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


async def record_failed_login(identifier: str) -> tuple[int, bool]:
    """Increment the failed-login counter for this identifier.

    Returns ``(current_count, just_crossed_threshold)``. The ``just_crossed``
    flag is True only on the exact attempt that pushes the count from BELOW
    threshold to AT/ABOVE threshold — so callers can emit one notification
    per burst rather than one per failure.

    Safe when Redis is unavailable: returns ``(0, False)`` and logs.
    """
    try:
        from app.redis_client import get_redis

        redis = await get_redis()
        if redis is None:
            return (0, False)
        key = f"{_FAILED_LOGIN_KEY_PREFIX}{_hash_identifier(identifier)}"
        new_count = await redis.incr(key)
        # First increment in a fresh window: arm the TTL. ``EXPIRE`` is
        # idempotent on subsequent increments — we don't refresh it on
        # every miss because that would let a slow attacker hold the
        # counter open indefinitely.
        if new_count == 1:
            await redis.expire(key, _FAILED_LOGIN_TTL_SECONDS)
        just_crossed = new_count == _BURST_THRESHOLD
        return (int(new_count), just_crossed)
    except Exception:
        logger.exception(
            "security_tracker: record_failed_login failed for %s",
            _hash_identifier(identifier),
        )
        return (0, False)


async def clear_failed_login(identifier: str) -> None:
    """Reset the counter on successful login.

    Safe when Redis is unavailable: no-ops and logs.
    """
    try:
        from app.redis_client import get_redis

        redis = await get_redis()
        if redis is None:
            return
        key = f"{_FAILED_LOGIN_KEY_PREFIX}{_hash_identifier(identifier)}"
        await redis.delete(key)
    except Exception:
        logger.exception("security_tracker: clear_failed_login failed")


def hash_identifier(identifier: str) -> str:
    """Public helper for callers that need a stable hash for dedup keys."""
    return _hash_identifier(identifier)
