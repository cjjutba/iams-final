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
    analytics,
    attendance,
    audit,
    auth,
    edge,
    edge_ws,
    face,
    hls,
    live_stream,
    notifications,
    presence,
    rooms,
    schedules,
    settings_router,
    users,
    webrtc,
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
    Application startup event handler

    Performs initialization tasks:
    - Check database connection
    - Load FAISS index (once face service is implemented)
    - Load InsightFace model (buffalo_l)
    """
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API prefix: {settings.API_PREFIX}")

    # Check database connection
    db_connected = check_db_connection()
    if not db_connected:
        logger.error("Failed to connect to database. Application may not function correctly.")
    else:
        logger.info("Database connection established")

    # Initialize Redis connection pool
    try:
        from app.redis_client import get_redis

        await get_redis()
        logger.info("Redis connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")

    # Start Redis pub/sub listener for WebSocket broadcast (multi-worker)
    try:
        from app.routers.websocket import manager

        await manager.start_redis_listener()
        logger.info("WebSocket Redis pub/sub listener started")
    except Exception as e:
        logger.error(f"Failed to start WebSocket Redis listener: {e}")

    # Load InsightFace model and FAISS index
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

        # Start background listener for FAISS reload notifications (multi-worker sync)
        import asyncio

        asyncio.create_task(faiss_manager.subscribe_index_changes())

        logger.info("Face recognition system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize face recognition: {e}")

    # Initialize APScheduler for continuous presence tracking
    try:
        from app.database import SessionLocal
        from app.services.presence_service import PresenceService

        logger.info("Initializing presence tracking scheduler...")

        # Create presence service instance (will be called by scheduler)
        async def run_presence_scan_cycle():
            """Background task to run presence scan cycles"""
            db = SessionLocal()
            try:
                presence_service = PresenceService(db)
                await presence_service.run_scan_cycle()
            except Exception as e:
                logger.error(f"Error in presence scan cycle: {e}")
            finally:
                db.close()

        # Schedule continuous presence tracking (every 60 seconds)
        scheduler.add_job(
            run_presence_scan_cycle,
            "interval",
            seconds=settings.SCAN_INTERVAL_SECONDS,
            id="presence_scan_cycle",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
        )

        # Periodic FAISS health check (every 30 minutes)
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

        # Auto-session scheduler: starts/ends sessions based on schedule times
        from app.services.session_scheduler import auto_manage_sessions

        scheduler.add_job(
            auto_manage_sessions,
            "interval",
            seconds=60,
            id="auto_session_manager",
            replace_existing=True,
            max_instances=1,
        )

        # Daily digest for faculty (8 PM Manila time, Mon-Sat)
        async def run_daily_digests():
            """Generate daily attendance digests for faculty."""
            db = SessionLocal()
            try:
                from app.routers.websocket import manager
                from app.services.digest_service import DigestService
                from app.services.notification_service import NotificationService

                email_svc = None
                if settings.EMAIL_ENABLED:
                    from app.services.email_service import EmailService
                    email_svc = EmailService()

                ns = NotificationService(manager, db, email_service=email_svc)
                ds = DigestService(db, notification_service=ns, email_service=email_svc)
                ds.generate_faculty_daily_digests()
            except Exception as e:
                logger.error(f"Daily digest error: {e}")
            finally:
                db.close()

        scheduler.add_job(
            run_daily_digests,
            "cron",
            hour=20,
            minute=0,
            timezone="Asia/Manila",
            id="daily_digest",
            replace_existing=True,
            max_instances=1,
        )

        # Weekly digest for students (Monday 8 AM Manila time)
        async def run_weekly_digests():
            """Generate weekly attendance digests for students."""
            db = SessionLocal()
            try:
                from app.routers.websocket import manager
                from app.services.digest_service import DigestService
                from app.services.notification_service import NotificationService

                email_svc = None
                if settings.EMAIL_ENABLED:
                    from app.services.email_service import EmailService
                    email_svc = EmailService()

                ns = NotificationService(manager, db, email_service=email_svc)
                ds = DigestService(db, notification_service=ns, email_service=email_svc)
                ds.generate_student_weekly_digests()
            except Exception as e:
                logger.error(f"Weekly digest error: {e}")
            finally:
                db.close()

        scheduler.add_job(
            run_weekly_digests,
            "cron",
            day_of_week="mon",
            hour=8,
            minute=0,
            timezone="Asia/Manila",
            id="weekly_digest",
            replace_existing=True,
            max_instances=1,
        )

        # Start the scheduler
        scheduler.start()
        logger.info(f"Presence tracking scheduler started (scan interval: {settings.SCAN_INTERVAL_SECONDS}s)")
        logger.info("Auto-session scheduler started (checks every 60s)")
        logger.info("Digest scheduler started (daily 8PM, weekly Mon 8AM)")

    except Exception as e:
        logger.error(f"Failed to initialize presence tracking scheduler: {e}")

    # Start mediamtx (WebRTC bridge: RTSP → WHEP)
    if settings.USE_WEBRTC_STREAMING:
        try:
            from app.services.mediamtx_service import mediamtx_service

            started = await mediamtx_service.start()
            if started:
                logger.info("WebRTC streaming ready (mediamtx running)")
            else:
                logger.warning("mediamtx failed to start — WebRTC unavailable, falling back to HLS")
        except Exception as e:
            logger.error(f"Failed to start mediamtx: {e}")

    # Create HLS segment directory (if HLS streaming enabled)
    if settings.USE_HLS_STREAMING:
        import os

        os.makedirs(settings.HLS_SEGMENT_DIR, exist_ok=True)
        logger.info(f"HLS streaming enabled (segment dir: {settings.HLS_SEGMENT_DIR})")

    # Start batch face processor (if enabled)
    if settings.USE_BATCH_PROCESSING:
        try:
            from app.services.batch_processor import batch_processor

            await batch_processor.start()
            logger.info("Batch face processor started")
        except Exception as e:
            logger.error(f"Failed to start batch processor: {e}")

    logger.info(f"{settings.APP_NAME} startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler

    Performs cleanup tasks:
    - Save FAISS index
    - Close database connections
    """
    logger.info(f"Shutting down {settings.APP_NAME}...")

    # Stop APScheduler
    try:
        if scheduler.running:
            logger.info("Stopping presence tracking scheduler...")
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")

    # Stop HLS and recognition services
    if settings.USE_HLS_STREAMING:
        try:
            from app.services.hls_service import hls_service
            from app.services.recognition_service import recognition_service

            logger.info("Stopping HLS and recognition services...")
            await hls_service.cleanup_all()
            await recognition_service.cleanup_all()
        except Exception as e:
            logger.error(f"Failed to stop HLS/recognition services: {e}")

    # Stop mediamtx
    if settings.USE_WEBRTC_STREAMING:
        try:
            from app.services.mediamtx_service import mediamtx_service

            logger.info("Stopping mediamtx...")
            mediamtx_service.stop()
        except Exception as e:
            logger.error(f"Failed to stop mediamtx: {e}")

    # Stop batch face processor
    if settings.USE_BATCH_PROCESSING:
        try:
            from app.services.batch_processor import batch_processor

            await batch_processor.stop()
            logger.info("Batch face processor stopped")
        except Exception as e:
            logger.error(f"Failed to stop batch processor: {e}")

    # Stop WebSocket Redis pub/sub listener
    try:
        from app.routers.websocket import manager

        await manager.stop_redis_listener()
    except Exception as e:
        logger.error(f"Failed to stop WebSocket Redis listener: {e}")

    # Close Redis connection pool
    try:
        from app.redis_client import close_redis

        await close_redis()
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


# ===== Health Check Endpoint =====


@app.get(f"{settings.API_PREFIX}/health", tags=["System"])
async def health_check():
    """
    Health check endpoint

    Returns the system status and version information.

    Returns:
        dict: Health status
    """
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0", "debug": settings.DEBUG}


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

# Auth routes
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])

# User routes
app.include_router(users.router, prefix=f"{settings.API_PREFIX}/users", tags=["Users"])

# Face recognition routes
app.include_router(face.router, prefix=f"{settings.API_PREFIX}/face", tags=["Face Recognition"])

# Room routes (edge device room lookup)
app.include_router(rooms.router, prefix=f"{settings.API_PREFIX}/rooms", tags=["Rooms"])

# Schedule routes
app.include_router(schedules.router, prefix=f"{settings.API_PREFIX}/schedules", tags=["Schedules"])

# Attendance routes
app.include_router(attendance.router, prefix=f"{settings.API_PREFIX}/attendance", tags=["Attendance"])

# Notification routes
app.include_router(notifications.router, prefix=f"{settings.API_PREFIX}/notifications", tags=["Notifications"])

# Presence tracking routes
app.include_router(presence.router, prefix=f"{settings.API_PREFIX}/presence", tags=["Presence Tracking"])

# Live Stream routes (WebSocket-based camera streaming)
app.include_router(live_stream.router, prefix=f"{settings.API_PREFIX}/stream", tags=["Live Stream"])

# HLS routes (serve .m3u8 playlists and .ts segments)
if settings.USE_HLS_STREAMING:
    app.include_router(hls.router, prefix=f"{settings.API_PREFIX}/hls", tags=["HLS Streaming"])

# WebRTC routes (WHEP signaling proxy + ICE config)
if settings.USE_WEBRTC_STREAMING:
    app.include_router(webrtc.router, prefix=f"{settings.API_PREFIX}/webrtc", tags=["WebRTC Streaming"])

# WebSocket routes
app.include_router(websocket.router, prefix=f"{settings.API_PREFIX}/ws", tags=["WebSocket"])

# Analytics routes
app.include_router(analytics.router, prefix=f"{settings.API_PREFIX}/analytics", tags=["Analytics"])

# Audit log routes
app.include_router(audit.router, prefix=f"{settings.API_PREFIX}/audit", tags=["Audit"])

# Edge device monitoring routes
app.include_router(edge.router, prefix=f"{settings.API_PREFIX}/edge", tags=["Edge Devices"])

# Edge device WebSocket routes (RPi detection relay)
app.include_router(edge_ws.router, prefix=f"{settings.API_PREFIX}/edge", tags=["Edge Devices"])

# System settings routes
app.include_router(settings_router.router, prefix=f"{settings.API_PREFIX}/settings", tags=["Settings"])


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
