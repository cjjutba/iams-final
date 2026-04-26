import asyncio
import contextlib
import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create the Redis connection pool.

    decode_responses=False: face embeddings are stored as raw bytes;
    callers handling text keys/channels must encode/decode explicitly.

    Includes a health check on the cached pool — if the connection is
    lost, the pool is torn down and recreated transparently.
    """
    global _redis_pool

    if _redis_pool is not None:
        try:
            await _redis_pool.ping()
            return _redis_pool
        except Exception as e:
            logger.warning("Redis connection lost, reconnecting...")
            # Best-effort admin-bell notification. Lazy import + broad
            # except so a failure to construct/emit never propagates into
            # the cache-warmup path. Dedup window: 10 min so a flapping
            # connection doesn't fan out a torrent of alerts.
            try:
                from app.services import health_notifier

                asyncio.create_task(
                    health_notifier.emit_one_shot(
                        title="Redis connection lost",
                        message=(
                            f"Redis is unreachable: {e}. Identity cache + "
                            "WS pub/sub degraded."
                        ),
                        notification_type="redis_connection_lost",
                        severity="error",
                        preference_key="ml_health_alerts",
                        reference_id="redis",
                        reference_type="cache",
                        dedup_window_seconds=600,
                    )
                )
            except Exception:
                logger.debug("redis_client: failed to schedule admin notify", exc_info=True)
            with contextlib.suppress(Exception):
                await _redis_pool.aclose()
            _redis_pool = None

    _redis_pool = redis.from_url(
        settings.REDIS_URL,
        decode_responses=False,
        max_connections=20,
    )
    await _redis_pool.ping()  # Fail fast if Redis is unreachable
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection closed")


async def health_check() -> bool:
    """Return True if Redis is reachable, False otherwise."""
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception:
        return False
