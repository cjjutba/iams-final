"""
IAMS Backend - FastAPI Application Entry Point

Main application file that initializes FastAPI, configures middleware,
registers routers, and handles application lifecycle events.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import logger, settings
from app.database import check_db_connection
from app.rate_limiter import limiter

# Import routers
from app.routers import (
    attendance,
    auth,
    face,
    health,
    notifications,
    presence,
    rooms,
    schedules,
    users,
    websocket,
)
from app.utils.exceptions import (
    IAMSError,
    generic_exception_handler,
    iams_exception_handler,
    validation_exception_handler,
)

# Global scheduler instance for background tasks
scheduler = AsyncIOScheduler()


# ===== FastAPI Application =====

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Attendance Monitoring System - Backend API",
    version="1.0.0",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    contact={
        "name": "IAMS Development Team",
        "email": "support@iams.jrmsu.edu.ph",
    },
    license_info={
        "name": "MIT",
    },
)

# Attach limiter to app state (required by slowapi)
app.state.limiter = limiter


# ===== CORS Middleware =====

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Exception Handlers =====

# Custom IAMS exceptions
app.add_exception_handler(IAMSError, iams_exception_handler)

# Pydantic validation errors
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Generic exception handler for unexpected errors
app.add_exception_handler(Exception, generic_exception_handler)

# Rate limit exceeded (429)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ===== Startup and Shutdown Events =====


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.

    - Check database connection
    - Initialize Redis
    - Load InsightFace model + FAISS index
    - Start BroadcastManager (WebSocket broadcaster)
    - Start APScheduler (presence scans, FAISS health check)
    """
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API prefix: {settings.API_PREFIX}")

    # ── Database ──────────────────────────────────────────────────
    db_connected = check_db_connection()
    if not db_connected:
        logger.error("Failed to connect to database. Application may not function correctly.")
    else:
        logger.info("Database connection established")

    # ── Redis ─────────────────────────────────────────────────────
    try:
        from app.redis_client import get_redis

        await get_redis()
        logger.info("Redis connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")

    # ── ML Models ─────────────────────────────────────────────────
    try:
        from app.services.ml.faiss_manager import faiss_manager
        from app.services.ml.insightface_model import insightface_model

        logger.info("Loading InsightFace model...")
        insightface_model.load_model()

        logger.info("Loading FAISS index...")
        faiss_manager.load_or_create_index()

        # Reconcile FAISS index with database
        try:
            from app.database import SessionLocal
            from app.services.face_service import FaceService

            db = SessionLocal()
            try:
                FaceService.reconcile_faiss_index(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"FAISS reconciliation failed: {e}")

        # Background listener for FAISS reload notifications (multi-worker sync)
        import asyncio

        asyncio.create_task(faiss_manager.subscribe_index_changes())

        logger.info("Face recognition system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize face recognition: {e}")

    # ── Frame Grabbers (attendance engine RTSP sources) ─────────────
    app.state.frame_grabbers = {}  # room_id -> FrameGrabber

    # ── WebSocket Broadcaster ─────────────────────────────────────
    try:
        from app.routers.websocket import get_broadcast_manager

        broadcaster = get_broadcast_manager()
        await broadcaster.start()
        logger.info("BroadcastManager started")
    except Exception as e:
        logger.error(f"Failed to start BroadcastManager: {e}")

    # ── APScheduler ───────────────────────────────────────────────
    try:
        import time as _time

        from app.database import SessionLocal
        from app.services.presence_service import PresenceService

        logger.info("Initializing APScheduler...")

        def _ensure_frame_grabber(app_instance, db_session, schedule):
            """Create FrameGrabber for an active session that lacks one."""
            from app.models.room import Room
            from app.services.frame_grabber import FrameGrabber

            room_id = str(schedule.room_id)
            room = db_session.query(Room).filter(Room.id == schedule.room_id).first()

            camera_url = room.camera_endpoint if room else None
            if not camera_url:
                logger.warning(f"No camera URL for room {room_id}, skipping FrameGrabber")
                return

            if room_id not in app_instance.state.frame_grabbers:
                grabber = FrameGrabber(camera_url)
                app_instance.state.frame_grabbers[room_id] = grabber
                logger.info(f"Auto-created FrameGrabber for room {room_id}")

        # Attendance scan cycle (every SCAN_INTERVAL_SECONDS, default 15s)
        # Uses AttendanceScanEngine when a FrameGrabber is available for a room,
        # otherwise falls back to pipeline Redis state.
        async def run_attendance_scan_cycle():
            """Background task: grab frames, run face recognition, feed presence service."""
            db = SessionLocal()
            try:
                presence_svc = PresenceService(db)
                scan_results: dict = {}

                for schedule_id, session in list(presence_svc._active_sessions.items()):
                    room_id = str(session.schedule.room_id)
                    grabber = app.state.frame_grabbers.get(room_id)

                    # Self-healing: create FrameGrabber if missing
                    if grabber is None:
                        try:
                            _ensure_frame_grabber(app, db, session.schedule)
                            grabber = app.state.frame_grabbers.get(room_id)
                        except Exception:
                            logger.exception(f"Failed to auto-create FrameGrabber for room {room_id}")

                    if grabber is None:
                        continue

                    try:
                        from app.services.attendance_engine import AttendanceScanEngine
                        from app.services.identity_cache import IdentityCache
                        from app.services.ml.faiss_manager import faiss_manager
                        from app.services.ml.insightface_model import insightface_model

                        # Self-heal FAISS: ensure index is loaded and user_map populated
                        if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
                            faiss_manager.load_or_create_index()
                        if not faiss_manager.user_map:
                            from app.services.face_service import FaceService
                            FaceService.reconcile_faiss_index(db)
                            logger.info(
                                f"FAISS self-healed: vectors={faiss_manager.index.ntotal}, "
                                f"mappings={len(faiss_manager.user_map)}"
                            )

                        engine = AttendanceScanEngine(
                            frame_grabber=grabber,
                            insightface_model=insightface_model,
                            faiss_manager=faiss_manager,
                        )
                        result = engine.scan_frame()
                        if result:
                            logger.info(
                                f"Attendance scan: room={room_id}, "
                                f"detected={result.detected_faces}, "
                                f"recognized={len(result.recognized)}, "
                                f"duration={result.scan_duration_ms:.0f}ms"
                            )
                            scan_results[room_id] = result
                            # Write to Redis identity cache for live feed
                            from app.redis_client import get_redis

                            # Look up student names for the identity cache
                            from app.models.user import User
                            identities = []
                            for r in result.recognized:
                                user = db.query(User).filter(User.id == r.user_id).first()
                                name = f"{user.first_name} {user.last_name}" if user else "Unknown"
                                identities.append({
                                    "user_id": r.user_id,
                                    "name": name,
                                    "student_id": user.student_id if user else "",
                                    "confidence": r.confidence,
                                    "bbox": list(r.bbox),
                                })

                            redis_client = await get_redis()
                            cache = IdentityCache(redis_client)
                            await cache.write_identities(room_id, schedule_id, identities)
                            await cache.write_scan_meta(room_id, schedule_id, {
                                "last_scan_ts": int(_time.time()),
                                "faces_detected": result.detected_faces,
                                "faces_recognized": len(result.recognized),
                            })
                    except Exception:
                        logger.exception(f"Attendance scan failed for room {room_id}")

                await presence_svc.run_scan_cycle(scan_results=scan_results)
            except Exception:
                logger.exception("Attendance scan cycle failed")
            finally:
                db.close()

        scheduler.add_job(
            run_attendance_scan_cycle,
            "interval",
            seconds=settings.SCAN_INTERVAL_SECONDS,
            id="presence_scan_cycle",
            replace_existing=True,
            max_instances=1,
        )

        # FAISS health check (every 30 minutes)
        async def run_faiss_health_check():
            """Compare FAISS vector count with DB active registrations."""
            db = SessionLocal()
            try:
                from app.repositories.face_repository import FaceRepository
                from app.services.ml.faiss_manager import faiss_manager as fm

                repo = FaceRepository(db)
                active_count = len(repo.get_active_embeddings())
                faiss_count = fm.index.ntotal if fm.index else 0
                if active_count != faiss_count:
                    logger.warning(
                        f"FAISS health check: mismatch detected — "
                        f"FAISS has {faiss_count} vectors, DB has {active_count} active registrations"
                    )
                else:
                    logger.debug(f"FAISS health check: in sync ({active_count} vectors)")
            except Exception as e:
                logger.error(f"FAISS health check failed: {e}")
            finally:
                db.close()

        scheduler.add_job(
            run_faiss_health_check,
            "interval",
            minutes=30,
            id="faiss_health_check",
            replace_existing=True,
            max_instances=1,
        )

        # Start the scheduler
        scheduler.start()
        logger.info(
            f"APScheduler started — presence scan every {settings.SCAN_INTERVAL_SECONDS}s, "
            f"FAISS health every 30m"
        )

    except Exception as e:
        logger.error(f"Failed to initialize APScheduler: {e}")

    logger.info(f"{settings.APP_NAME} startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.

    Stops all background services and cleans up resources.
    """
    logger.info(f"Shutting down {settings.APP_NAME}...")

    # Stop APScheduler
    try:
        if scheduler.running:
            logger.info("Stopping APScheduler...")
            scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")

    # Stop all FrameGrabbers
    if hasattr(app.state, "frame_grabbers"):
        for room_id, grabber in list(app.state.frame_grabbers.items()):
            try:
                grabber.stop()
                logger.info(f"FrameGrabber stopped for room {room_id}")
            except Exception as e:
                logger.error(f"Failed to stop FrameGrabber for room {room_id}: {e}")
        app.state.frame_grabbers.clear()

    # Stop BroadcastManager
    try:
        from app.routers.websocket import get_broadcast_manager

        broadcaster = get_broadcast_manager()
        await broadcaster.stop()
        logger.info("BroadcastManager stopped")
    except Exception as e:
        logger.error(f"Failed to stop BroadcastManager: {e}")

    # Close Redis connection pool
    try:
        from app.redis_client import close_redis

        await close_redis()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Failed to close Redis: {e}")

    # Save FAISS index
    try:
        from app.services.ml.faiss_manager import faiss_manager

        logger.info("Saving FAISS index...")
        faiss_manager.save()
    except Exception as e:
        logger.error(f"Failed to save FAISS index: {e}")

    logger.info(f"{settings.APP_NAME} shutdown complete")


# ===== Health Check =====

# Deep health check is registered below via health.router at /api/v1/health


@app.get("/", tags=["System"])
async def root(request: Request):
    """
    Root endpoint

    When accessed by a browser, serves a small HTML page that detects
    Supabase auth callback hash fragments (#access_token=...) and
    redirects to the proper email-confirmed landing page.
    API clients (no text/html accept) get JSON.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        redirect_target = f"{settings.API_PREFIX}/auth/email-confirmed"
        return HTMLResponse(
            content=f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>IAMS</title></head>
<body>
<p id="msg" style="font-family:sans-serif;padding:40px">Loading&hellip;</p>
<script>
var h = window.location.hash;
if (h && (h.includes('access_token') || h.includes('error='))) {{
  window.location.replace('{redirect_target}' + h);
}} else {{
  document.getElementById('msg').textContent = 'IAMS API is running';
}}
</script></body></html>"""
        )
    return {"message": f"{settings.APP_NAME} API is running", "docs": f"{settings.API_PREFIX}/docs"}


# ===== Router Includes =====

API_PREFIX = settings.API_PREFIX

app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["Users"])
app.include_router(face.router, prefix=f"{API_PREFIX}/face", tags=["Face"])
app.include_router(rooms.router, prefix=f"{API_PREFIX}/rooms", tags=["Rooms"])
app.include_router(schedules.router, prefix=f"{API_PREFIX}/schedules", tags=["Schedules"])
app.include_router(attendance.router, prefix=f"{API_PREFIX}/attendance", tags=["Attendance"])
app.include_router(presence.router, prefix=f"{API_PREFIX}/presence", tags=["Presence"])
app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications", tags=["Notifications"])
app.include_router(websocket.router, prefix=f"{API_PREFIX}/ws", tags=["WebSocket"])
app.include_router(health.router, prefix=f"{API_PREFIX}/health", tags=["Health"])


# ===== Development Server =====

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
    )
