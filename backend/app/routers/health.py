"""
Deep Health Check Endpoint

Comprehensive system health check used by Docker HEALTHCHECK and the
monitoring dashboard.  Checks all critical and optional components:

  - Database connectivity + latency
  - Redis connectivity + latency + active stream count
  - FAISS index status (vector count)
  - mediamtx status (process + API)
  - Edge device connections
  - Worker metrics (from stream:metrics in Redis)

Overall status logic:
  - "healthy"   : all critical components (DB, Redis) are up
  - "degraded"  : critical components up but optional ones (mediamtx, FAISS,
                   edge devices, workers) are down
  - "unhealthy" : any critical component is down
"""

import logging
import time

from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Track when the process started for uptime calculation
_process_start_time = time.time()


async def _check_database() -> dict:
    """Check database connectivity and measure latency."""
    try:
        from app.database import SessionLocal

        from sqlalchemy import text

        start = time.monotonic()
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {"status": "healthy", "latency_ms": latency_ms}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Health check — database error: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def _check_redis() -> dict:
    """Check Redis connectivity, latency, and active stream count."""
    try:
        from app.redis_client import get_redis

        r = await get_redis()

        # Ping for latency
        start = time.monotonic()
        await r.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 1)

        # Count active streams (stream:frames:*, stream:detections:*, etc.)
        active_streams = 0
        async for key in r.scan_iter(match=b"stream:*"):
            key_type = await r.type(key)
            decoded_type = key_type.decode() if isinstance(key_type, bytes) else key_type
            if decoded_type == "stream":
                active_streams += 1

        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "active_streams": active_streams,
        }
    except Exception as e:
        logger.error(f"Health check — Redis error: {e}")
        return {"status": "unhealthy", "error": str(e)}


def _check_faiss() -> dict:
    """Check FAISS index status."""
    try:
        from app.services.ml.faiss_manager import faiss_manager

        if faiss_manager.index is None:
            return {"status": "unhealthy", "error": "Index not initialized"}

        return {
            "status": "healthy",
            "vectors": faiss_manager.index.ntotal,
            "user_mappings": len(faiss_manager.user_map),
        }
    except Exception as e:
        logger.error(f"Health check — FAISS error: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def _check_mediamtx() -> dict:
    """Check mediamtx status (disabled — pipeline removed in architecture redesign)."""
    return {"status": "disabled"}


def _check_edge_devices() -> dict:
    """Check connected edge devices (edge_ws removed in architecture redesign)."""
    return {"status": "no_devices", "connected": 0}


async def _check_workers() -> dict:
    """Check worker status (workers removed in architecture redesign)."""
    return {"status": "no_workers"}


@router.get("", tags=["System"])
async def deep_health_check():
    """
    Deep health check endpoint.

    Checks all system components and returns comprehensive status.
    Used by Docker HEALTHCHECK (every 30s) and the monitoring dashboard.

    Returns:
        Detailed health status for all components.
    """
    # Run all checks (DB and Redis are critical, others are optional)
    db_status = await _check_database()
    redis_status = await _check_redis()
    faiss_status = _check_faiss()
    mediamtx_status = await _check_mediamtx()
    edge_status = _check_edge_devices()
    worker_status = await _check_workers()

    # Determine overall status
    critical_healthy = (
        db_status.get("status") == "healthy"
        and redis_status.get("status") == "healthy"
    )

    optional_statuses = [
        faiss_status.get("status"),
        mediamtx_status.get("status"),
    ]
    # "disabled" and "no_devices" / "no_workers" are not failures
    optional_ok = all(
        s in ("healthy", "disabled", "no_devices", "no_workers")
        for s in optional_statuses
    )

    if not critical_healthy:
        overall = "unhealthy"
    elif not optional_ok:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "role": settings.SERVICE_ROLE,
        "uptime_seconds": int(time.time() - _process_start_time),
        "components": {
            "database": db_status,
            "redis": redis_status,
            "faiss": faiss_status,
            "mediamtx": mediamtx_status,
            "edge_devices": edge_status,
            "workers": worker_status,
        },
    }
