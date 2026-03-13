import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create the Redis connection pool.

    decode_responses=False: face embeddings are stored as raw bytes;
    callers handling text keys/channels must encode/decode explicitly.
    """
    global _redis_pool
    if _redis_pool is None:
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
