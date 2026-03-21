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

    # ── Frame Grabbers & Session Pipelines ────────────────────────
    app.state.frame_grabbers = {}  # room_id -> FrameGrabber
    app.state.session_pipelines = {}  # schedule_id -> SessionPipeline

    # ── WebSocket Redis subscriber ─────────────────────────────
    try:
        from app.routers.websocket import ws_manager

        await ws_manager.start_redis_subscriber()
    except Exception as e:
        logger.warning(f"Redis WS subscriber not started: {e}")

    # ── APScheduler ───────────────────────────────────────────────
    try:
        from app.database import SessionLocal
        from app.services.presence_service import PresenceService

        logger.info("Initializing APScheduler...")

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

        # Session lifecycle management — creates/stops SessionPipelines
        async def run_session_lifecycle_check():
            """Auto-start/end sessions and their real-time pipelines."""
            from datetime import datetime

            from app.models.room import Room
            from app.repositories.schedule_repository import ScheduleRepository
            from app.services.frame_grabber import FrameGrabber
            from app.services.realtime_pipeline import SessionPipeline

            db = SessionLocal()
            try:
                now = datetime.now()
                current_day = now.weekday()
                current_time = now.time()

                schedule_repo = ScheduleRepository(db)

                # Track which sessions the OLD PresenceService knows about
                # (kept for backward compat during migration)
                presence_svc = PresenceService(db)
                PresenceService.cleanup_old_ended_sessions()
                active_session_ids = set(presence_svc.get_active_sessions())
                pipeline_ids = set(app.state.session_pipelines.keys())

                # Merge both sets — a session is "active" if either system has it
                all_active = active_session_ids | pipeline_ids

                # === Auto-start ===
                should_be_active = schedule_repo.get_active_at_time(current_day, current_time)
                for schedule in should_be_active:
                    sid = str(schedule.id)
                    if sid in all_active or PresenceService.was_session_ended_today(sid):
                        continue

                    room_id = str(schedule.room_id)
                    room = db.query(Room).filter(Room.id == schedule.room_id).first()
                    camera_url = room.camera_endpoint if room else None

                    try:
                        # Start legacy session (keeps old code path working)
                        await presence_svc.start_session(sid)

                        # Create FrameGrabber if we have a camera
                        if camera_url and room_id not in app.state.frame_grabbers:
                            grabber = FrameGrabber(camera_url)
                            app.state.frame_grabbers[room_id] = grabber
                            logger.info(f"[lifecycle] Created FrameGrabber for room {room_id}")

                        # Start real-time pipeline
                        grabber = app.state.frame_grabbers.get(room_id)
                        if grabber:
                            # Self-heal FAISS before starting pipeline
                            from app.services.ml.faiss_manager import faiss_manager

                            if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
                                faiss_manager.load_or_create_index()
                            if not faiss_manager.user_map:
                                from app.services.face_service import FaceService
                                FaceService.reconcile_faiss_index(db)

                            pipeline = SessionPipeline(
                                schedule_id=sid,
                                grabber=grabber,
                                db_factory=SessionLocal,
                            )
                            await pipeline.start()
                            app.state.session_pipelines[sid] = pipeline
                            logger.info(
                                f"[lifecycle] Started pipeline for "
                                f"{schedule.subject_code} ({sid})"
                            )
                        else:
                            logger.warning(
                                f"[lifecycle] No camera for {schedule.subject_code}, "
                                f"session started without pipeline"
                            )

                    except Exception:
                        logger.exception(f"[lifecycle] Failed to start session {sid}")

                # === Auto-end ===
                for sid in list(all_active):
                    # Check legacy session state first
                    session_state = presence_svc.get_session_state(sid)
                    if not session_state:
                        # Pipeline might be running without legacy session
                        if sid in pipeline_ids:
                            # Let it keep running — it manages its own state
                            pass
                        continue

                    schedule = session_state.schedule
                    if current_time <= schedule.end_time:
                        continue

                    room_id = str(schedule.room_id)
                    subject_code = schedule.subject_code

                    try:
                        # Stop pipeline first
                        pipeline = app.state.session_pipelines.pop(sid, None)
                        if pipeline:
                            await pipeline.stop()
                            logger.info(f"[lifecycle] Stopped pipeline for {subject_code}")

                        # End legacy session
                        await presence_svc.end_session(sid)
                        logger.info(f"[lifecycle] Ended session for {subject_code} ({sid})")

                        # Stop FrameGrabber
                        frame_grabbers = app.state.frame_grabbers
                        if room_id in frame_grabbers:
                            frame_grabbers[room_id].stop()
                            del frame_grabbers[room_id]
                            logger.info(f"[lifecycle] Stopped FrameGrabber for room {room_id}")

                    except Exception:
                        logger.exception(f"[lifecycle] Failed to end session {sid}")

            except Exception:
                logger.exception("[lifecycle] Session lifecycle check failed")
            finally:
                db.close()

        scheduler.add_job(
            run_session_lifecycle_check,
            "interval",
            seconds=30,
            id="session_lifecycle_check",
            replace_existing=True,
            max_instances=1,
        )

        # Start the scheduler
        scheduler.start()
        logger.info(
            "APScheduler started — session lifecycle every 30s, FAISS health every 30m"
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

    # Stop all SessionPipelines
    if hasattr(app.state, "session_pipelines"):
        for sid, pipeline in list(app.state.session_pipelines.items()):
            try:
                await pipeline.stop()
                logger.info(f"SessionPipeline stopped for schedule {sid}")
            except Exception as e:
                logger.error(f"Failed to stop pipeline for schedule {sid}: {e}")
        app.state.session_pipelines.clear()

    # Stop all FrameGrabbers
    if hasattr(app.state, "frame_grabbers"):
        for room_id, grabber in list(app.state.frame_grabbers.items()):
            try:
                grabber.stop()
                logger.info(f"FrameGrabber stopped for room {room_id}")
            except Exception as e:
                logger.error(f"Failed to stop FrameGrabber for room {room_id}: {e}")
        app.state.frame_grabbers.clear()

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
