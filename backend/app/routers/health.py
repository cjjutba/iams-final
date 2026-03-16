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

import json
import logging
import time

import httpx
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
    """Check mediamtx process status and API availability."""
    if not settings.USE_WEBRTC_STREAMING:
        return {"status": "disabled"}

    try:
        from app.services.mediamtx_service import mediamtx_service

        process_alive = mediamtx_service.is_healthy() or settings.MEDIAMTX_EXTERNAL

        # Try to hit the mediamtx REST API for path info
        url = f"{settings.MEDIAMTX_API_URL}/v3/paths/list"
        active_paths = 0
        api_reachable = False

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    api_reachable = True
                    data = resp.json()
                    # mediamtx v3 returns {"items": [...]}
                    items = data.get("items") or []
                    active_paths = len([
                        p for p in items
                        if p.get("ready", False) or p.get("readers", 0) > 0
                    ])
        except Exception:
            pass

        if not process_alive and not api_reachable:
            return {"status": "unhealthy", "error": "Process not running and API unreachable"}

        return {
            "status": "healthy" if api_reachable else "degraded",
            "process_alive": process_alive,
            "api_reachable": api_reachable,
            "active_paths": active_paths,
        }
    except Exception as e:
        logger.error(f"Health check — mediamtx error: {e}")
        return {"status": "unhealthy", "error": str(e)}


def _check_edge_devices() -> dict:
    """Check connected edge devices."""
    try:
        from app.routers.edge_ws import get_edge_devices

        devices = get_edge_devices()
        now = time.time()

        device_info = {}
        for room_id, info in devices.items():
            last_hb = info.get("last_heartbeat", 0)
            device_info[room_id] = {
                "connected_at": info.get("connected_at"),
                "last_heartbeat_seconds_ago": round(now - last_hb, 1) if last_hb else None,
                "frames_received": info.get("frames_received", 0),
                "camera_status": info.get("camera_status", "unknown"),
            }

        connected = len(devices)
        return {
            "status": "healthy" if connected > 0 else "no_devices",
            "connected": connected,
            "devices": device_info,
        }
    except Exception as e:
        logger.error(f"Health check — edge devices error: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def _check_workers() -> dict:
    """Check worker status from stream:metrics in Redis (last 30s)."""
    try:
        from app.redis_client import get_redis
        from app.services.stream_bus import STREAM_METRICS

        r = await get_redis()

        # Read the most recent metrics messages (last 50 entries)
        entries = await r.xrevrange(STREAM_METRICS, count=50)

        now = time.time()
        cutoff = now - 30  # Only consider metrics from the last 30 seconds
        workers: dict[str, dict] = {}

        for msg_id, fields in entries:
            data_raw = fields.get(b"data") or fields.get("data")
            ts_raw = fields.get(b"ts") or fields.get("ts")

            if not data_raw:
                continue

            if isinstance(data_raw, bytes):
                data_raw = data_raw.decode()
            if isinstance(ts_raw, bytes):
                ts_raw = ts_raw.decode()

            ts = float(ts_raw) if ts_raw else 0
            if ts < cutoff:
                continue

            data = json.loads(data_raw)
            worker_name = data.get("worker", "unknown")

            # Keep only the latest metrics per worker
            if worker_name not in workers:
                workers[worker_name] = {
                    "status": "healthy",
                    "frames_processed": data.get("frames_processed", 0),
                    "errors": data.get("errors", 0),
                    "uptime_seconds": data.get("uptime_seconds", 0),
                    "last_report_seconds_ago": round(now - ts, 1),
                }

        if not workers:
            return {"status": "no_workers"}

        return workers
    except Exception as e:
        logger.error(f"Health check — workers error: {e}")
        return {"status": "unhealthy", "error": str(e)}


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
