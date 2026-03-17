"""
IAMS Backend - FastAPI Application Entry Point

Main application file that initializes FastAPI, configures middleware,
registers routers, and handles application lifecycle events.

Supports role-based startup via settings.SERVICE_ROLE:
  - "api-gateway"  : FastAPI + PipelineManager + BroadcastManager + mediamtx + APScheduler
  - "all" (default, dev): Same as api-gateway (everything in one process)
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
    health,
    live_stream,
    notifications,
    pipeline,
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

# Roles that run the full API gateway stack
_GATEWAY_ROLES = {"api-gateway", "all"}


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

    For api-gateway / all roles:
    - Check database connection
    - Initialize Redis
    - Load InsightFace model + FAISS index
    - Start PipelineManager (video pipeline orchestrator)
    - Start BroadcastManager (WebSocket broadcaster)
    - Start mediamtx (WebRTC bridge)
    - Start APScheduler (presence scans, session management, digests)
    """
    role = settings.SERVICE_ROLE
    logger.info(f"Starting {settings.APP_NAME} (role={role})...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API prefix: {settings.API_PREFIX}")

    if role not in _GATEWAY_ROLES:
        logger.info(f"Role '{role}' — skipping gateway startup (workers start via __main__)")
        return

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

    # ── Video Pipeline Manager ──────────────────────────────────────
    if settings.PIPELINE_ENABLED:
        try:
            from app.pipeline.pipeline_manager import PipelineManager
            pipeline_manager = PipelineManager(redis_url=settings.REDIS_URL)
            app.state.pipeline_manager = pipeline_manager
            logger.info("PipelineManager initialized (pipelines start on session start)")
        except Exception as e:
            logger.error(f"Failed to initialize PipelineManager: {e}")

    # ── WebSocket Broadcaster ─────────────────────────────────────
    try:
        from app.routers.websocket import get_broadcast_manager

        broadcaster = get_broadcast_manager()
        await broadcaster.start()
        logger.info("BroadcastManager started")
    except Exception as e:
        logger.error(f"Failed to start BroadcastManager: {e}")

    # ── mediamtx (WebRTC bridge: RTSP -> WHEP) ────────────────────
    if settings.USE_WEBRTC_STREAMING:
        try:
            from app.services.mediamtx_service import mediamtx_service

            started = await mediamtx_service.start()
            if started:
                logger.info("WebRTC streaming ready (mediamtx running)")
            else:
                logger.warning("mediamtx failed to start — WebRTC unavailable")
        except Exception as e:
            logger.error(f"Failed to start mediamtx: {e}")

    # ── APScheduler ───────────────────────────────────────────────
    try:
        import time as _time

        from app.database import SessionLocal
        from app.services.presence_service import PresenceService
        from app.services.session_scheduler import auto_manage_sessions

        logger.info("Initializing APScheduler...")

        def _ensure_room_infrastructure(app_instance, db_session, schedule, schedule_id):
            """Create FrameGrabber + pipeline for an active session that lacks them."""
            from app.models.room import Room
            from app.services.camera_config import get_camera_url
            from app.services.frame_grabber import FrameGrabber

            room_id = str(schedule.room_id)
            room = db_session.query(Room).filter(Room.id == schedule.room_id).first()
            stream_key = room.stream_key if room and room.stream_key else room_id

            # Use mediamtx local RTSP as frame source (handles H.265 → decoded frames)
            mediamtx_url = f"{settings.MEDIAMTX_RTSP_URL}/{stream_key}/raw"
            # Also get direct camera URL as fallback
            camera_url = get_camera_url(room_id, db_session) or mediamtx_url

            # Create FrameGrabber (reads from mediamtx, not direct camera)
            if room_id not in app_instance.state.frame_grabbers:
                grabber = FrameGrabber(mediamtx_url)
                app_instance.state.frame_grabbers[room_id] = grabber
                logger.info(f"Auto-created FrameGrabber for room {room_id} ({mediamtx_url})")

            # Start pipeline (reads from camera/mediamtx, publishes annotated H.264)
            mgr = getattr(app_instance.state, "pipeline_manager", None)
            if mgr and settings.PIPELINE_ENABLED:
                status_list = mgr.get_status()
                already_running = any(p.get("room_id") == room_id and p.get("alive") for p in status_list)
                if not already_running:
                    pipeline_config = {
                        "room_id": room_id,
                        "rtsp_source": camera_url,
                        "rtsp_target": f"{settings.MEDIAMTX_RTSP_URL}/{stream_key}/annotated",
                        "width": settings.PIPELINE_WIDTH,
                        "height": settings.PIPELINE_HEIGHT,
                        "fps": settings.PIPELINE_FPS,
                        "room_name": room.name if room else "",
                        "subject": schedule.subject_code or "",
                        "professor": "",
                        "total_enrolled": 0,
                        "session_id": schedule_id,
                        "det_model": settings.PIPELINE_DET_MODEL,
                    }
                    mgr.start_pipeline(pipeline_config)
                    logger.info(f"Auto-started pipeline for room {room_id}")

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

                    # Self-healing: create FrameGrabber + pipeline for active sessions
                    # that were started before the current code was deployed
                    if grabber is None:
                        try:
                            _ensure_room_infrastructure(app, db, session.schedule, schedule_id)
                            grabber = app.state.frame_grabbers.get(room_id)
                        except Exception:
                            logger.exception(f"Failed to auto-create infrastructure for room {room_id}")

                    if grabber is None:
                        continue

                    try:
                        from app.services.attendance_engine import AttendanceScanEngine
                        from app.services.identity_cache import IdentityCache
                        from app.services.ml.faiss_manager import faiss_manager
                        from app.services.ml.insightface_model import insightface_model

                        engine = AttendanceScanEngine(
                            frame_grabber=grabber,
                            insightface_model=insightface_model,
                            faiss_manager=faiss_manager,
                        )
                        result = engine.scan_frame()
                        if result:
                            scan_results[room_id] = result
                            # Write to Redis identity cache for live feed pipeline
                            from app.redis_client import get_redis

                            redis_client = await get_redis()
                            cache = IdentityCache(redis_client)
                            await cache.write_identities(room_id, schedule_id, [
                                {
                                    "user_id": r.user_id,
                                    "name": "",
                                    "confidence": r.confidence,
                                    "bbox": list(r.bbox),
                                }
                                for r in result.recognized
                            ])
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

        # Auto-session scheduler: starts/ends sessions based on schedule times
        scheduler.add_job(
            auto_manage_sessions,
            "interval",
            seconds=60,
            id="auto_session_manager",
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

        # Daily digest for faculty (8 PM Manila time, Mon-Sat)
        async def run_daily_digests():
            """Generate daily attendance digests for faculty."""
            db = SessionLocal()
            try:
                from app.routers.websocket import get_broadcast_manager
                from app.services.digest_service import DigestService
                from app.services.notification_service import NotificationService

                email_svc = None
                if settings.EMAIL_ENABLED:
                    from app.services.email_service import EmailService

                    email_svc = EmailService()

                broadcaster = get_broadcast_manager()
                ns = NotificationService(broadcaster, db, email_service=email_svc)
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
                from app.routers.websocket import get_broadcast_manager
                from app.services.digest_service import DigestService
                from app.services.notification_service import NotificationService

                email_svc = None
                if settings.EMAIL_ENABLED:
                    from app.services.email_service import EmailService

                    email_svc = EmailService()

                broadcaster = get_broadcast_manager()
                ns = NotificationService(broadcaster, db, email_service=email_svc)
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
        logger.info(f"APScheduler started — presence scan every {settings.SCAN_INTERVAL_SECONDS}s, "
                     f"session management every 60s, FAISS health every 30m")
        logger.info("Digest scheduler started (daily 8PM, weekly Mon 8AM)")

    except Exception as e:
        logger.error(f"Failed to initialize APScheduler: {e}")

    logger.info(f"{settings.APP_NAME} startup complete (role={role})")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.

    Stops all background services and cleans up resources.
    """
    role = settings.SERVICE_ROLE
    logger.info(f"Shutting down {settings.APP_NAME} (role={role})...")

    if role not in _GATEWAY_ROLES:
        logger.info(f"Role '{role}' — nothing to tear down in main.py")
        return

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

    # Stop Pipeline Manager
    if hasattr(app.state, "pipeline_manager"):
        try:
            app.state.pipeline_manager.stop_all()
            logger.info("All video pipelines stopped")
        except Exception as e:
            logger.error(f"Failed to stop pipelines: {e}")

    # Stop BroadcastManager
    try:
        from app.routers.websocket import get_broadcast_manager

        broadcaster = get_broadcast_manager()
        await broadcaster.stop()
        logger.info("BroadcastManager stopped")
    except Exception as e:
        logger.error(f"Failed to stop BroadcastManager: {e}")

    # Stop mediamtx
    if settings.USE_WEBRTC_STREAMING:
        try:
            from app.services.mediamtx_service import mediamtx_service

            logger.info("Stopping mediamtx...")
            mediamtx_service.stop()
        except Exception as e:
            logger.error(f"Failed to stop mediamtx: {e}")

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

# Live Stream WebSocket (signaling + detection metadata for mobile)
app.include_router(live_stream.router, prefix=f"{settings.API_PREFIX}/ws/stream", tags=["Live Stream"])

# WebRTC routes (WHEP signaling proxy + ICE config)
app.include_router(webrtc.router, prefix=f"{settings.API_PREFIX}/webrtc", tags=["WebRTC Streaming"])

# WebSocket routes (attendance + alerts broadcast)
app.include_router(websocket.router, prefix=f"{settings.API_PREFIX}/ws", tags=["WebSocket"])

# Analytics routes
app.include_router(analytics.router, prefix=f"{settings.API_PREFIX}/analytics", tags=["Analytics"])

# Audit log routes
app.include_router(audit.router, prefix=f"{settings.API_PREFIX}/audit", tags=["Audit"])

# Edge device monitoring routes
app.include_router(edge.router, prefix=f"{settings.API_PREFIX}/edge", tags=["Edge Devices"])

# Edge device WebSocket routes (RPi frame ingestion)
app.include_router(edge_ws.router, prefix=f"{settings.API_PREFIX}/ws/edge", tags=["Edge Devices"])

# System settings routes
app.include_router(settings_router.router, prefix=f"{settings.API_PREFIX}/settings", tags=["Settings"])

# Health check (deep system status for Docker HEALTHCHECK + monitoring dashboard)
app.include_router(health.router, prefix=f"{settings.API_PREFIX}/health", tags=["System"])

# Video pipeline management (start/stop/status)
app.include_router(pipeline.router, prefix=f"{settings.API_PREFIX}/pipeline", tags=["Pipeline"])


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
