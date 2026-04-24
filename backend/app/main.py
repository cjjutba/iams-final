"""
IAMS Backend - FastAPI Application Entry Point

Main application file that initializes FastAPI, configures middleware,
registers routers, and handles application lifecycle events.
"""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import logger, settings
from app.database import check_db_connection, init_db
from app.rate_limiter import limiter

# Import routers. Router modules are cheap to import (pure FastAPI APIRouter
# declarations + Pydantic schemas) — we import them all unconditionally and
# then conditionally register below based on settings.ENABLE_*_ROUTES.
# Service modules with heavy deps (insightface, faiss, onnxruntime) are
# imported lazily inside the lifespan + on-demand helper so the VPS thin
# profile never pays their import cost.
from app.routers import (
    activity,
    analytics,
    attendance,
    audit,
    auth,
    edge_devices,
    face,
    health,
    notifications,
    presence,
    recognitions,
    rooms,
    schedules,
    settings_router,
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


# ===== Lifespan Context Manager =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Startup (before yield):
    - Check database connection
    - Initialize Redis
    - Load InsightFace model + FAISS index
    - Start APScheduler (presence scans, FAISS health check)

    Shutdown (after yield):
    - Stop scheduler, pipelines, frame grabbers
    - Close Redis connection
    - Save FAISS index
    """
    # ===================================================================
    # STARTUP
    # ===================================================================
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API prefix: {settings.API_PREFIX}")

    # ── Database ──────────────────────────────────────────────────
    db_connected = await asyncio.to_thread(check_db_connection)
    if not db_connected:
        raise RuntimeError("Database connection failed. Cannot start application.")

    # Ensure all tables exist (creates any missing tables)
    await asyncio.to_thread(init_db)
    logger.info("Database connection established")

    # ── Redis ─────────────────────────────────────────────────────
    if settings.ENABLE_REDIS:
        try:
            from app.redis_client import get_redis

            await get_redis()
            logger.info("Redis connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
    else:
        logger.info("Redis disabled (ENABLE_REDIS=false)")

    # ── ML Models ─────────────────────────────────────────────────
    if settings.ENABLE_ML:
        try:
            from app.services.ml.faiss_manager import faiss_manager
            from app.services.ml.insightface_model import insightface_model

            logger.info("Loading InsightFace model...")
            insightface_model.load_model()

            logger.info("Loading FAISS index...")
            faiss_manager.load_or_create_index()
            faiss_manager.rebuild_user_map_from_db()

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
            app.state.faiss_subscriber_task = asyncio.create_task(faiss_manager.subscribe_index_changes())

            logger.info("Face recognition system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize face recognition: {e}")

        # ── Recognition-evidence writer ────────────────────────
        # Starts only when both ML and evidence capture are enabled. Drains
        # on shutdown; see docs/plans/2026-04-22-recognition-evidence.
        if settings.ENABLE_RECOGNITION_EVIDENCE:
            try:
                from app.services.evidence_writer import evidence_writer

                await evidence_writer.start()
            except Exception as e:
                logger.error(f"Failed to start evidence writer: {e}")
        else:
            logger.info(
                "Recognition evidence capture disabled (ENABLE_RECOGNITION_EVIDENCE=false)"
            )
    else:
        logger.info("ML disabled (ENABLE_ML=false) — skipping InsightFace + FAISS load")

    # ── Frame Grabbers & Session Pipelines ────────────────────────
    # State dicts are allocated unconditionally so the on-demand + lifecycle
    # helpers can check them without an AttributeError. When ENABLE_FRAME_GRABBERS
    # is false they stay empty.
    app.state.frame_grabbers = {}  # room_id -> FrameGrabber
    app.state.session_pipelines = {}  # schedule_id -> SessionPipeline

    # ── WebSocket Redis subscriber ─────────────────────────────
    if settings.ENABLE_WS_ROUTES and settings.ENABLE_REDIS:
        try:
            from app.routers.websocket import ws_manager

            await ws_manager.start_redis_subscriber()
        except Exception as e:
            logger.warning(f"Redis WS subscriber not started: {e}")
    else:
        logger.info(
            "WS Redis subscriber skipped "
            f"(ENABLE_WS_ROUTES={settings.ENABLE_WS_ROUTES}, ENABLE_REDIS={settings.ENABLE_REDIS})"
        )

    # ── APScheduler ───────────────────────────────────────────────
    # Skipped in the VPS thin profile: without ML + frame grabbers + presence
    # + notifications, every scheduled job would either no-op or reference
    # modules that are intentionally unused on the VPS. Raising a sentinel
    # exception inside the existing try: block skips the block without having
    # to re-indent hundreds of lines.
    class _SkipBackgroundJobs(Exception):
        pass

    try:
        if not settings.ENABLE_BACKGROUND_JOBS:
            raise _SkipBackgroundJobs
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
            misfire_grace_time=300,
            coalesce=True,
        )

        # Session lifecycle management — creates/stops SessionPipelines
        async def run_session_lifecycle_check():
            """Auto-start/end sessions and their real-time pipelines."""
            from datetime import datetime

            from app.models.room import Room
            from app.repositories.schedule_repository import ScheduleRepository
            from app.services.frame_grabber import FrameGrabber
            from app.services.realtime_pipeline import SessionPipeline

            # --- Sync helper: gather DB state for auto-start/end decisions ---
            def _gather_lifecycle_state():
                """Run all synchronous DB reads in a single call."""
                from app.models.enrollment import Enrollment

                db = SessionLocal()
                try:
                    now = datetime.now()
                    current_day = now.weekday()
                    current_time = now.time()

                    schedule_repo = ScheduleRepository(db)
                    presence_svc = PresenceService(db)
                    PresenceService.cleanup_old_ended_sessions()
                    active_session_ids = set(presence_svc.get_active_sessions())

                    # Schedules that should be active right now
                    should_be_active = schedule_repo.get_active_at_time(current_day, current_time)

                    # Build list of schedules to start with their room info
                    to_start = []
                    pipeline_ids = set(app.state.session_pipelines.keys())
                    all_active = active_session_ids | pipeline_ids
                    for schedule in should_be_active:
                        sid = str(schedule.id)
                        if sid in all_active or PresenceService.was_session_ended_today(sid):
                            continue
                        room_id = str(schedule.room_id)
                        room = db.query(Room).filter(Room.id == schedule.room_id).first()
                        camera_url = room.camera_endpoint if room else None

                        # Fetch faculty_id and enrolled student_ids for notifications
                        faculty_id = str(schedule.faculty_id)
                        student_ids = [
                            str(e.student_id)
                            for e in db.query(Enrollment.student_id).filter(Enrollment.schedule_id == schedule.id).all()
                        ]

                        to_start.append(
                            {
                                "sid": sid,
                                "room_id": room_id,
                                "camera_url": camera_url,
                                "subject_code": schedule.subject_code,
                                "faculty_id": faculty_id,
                                "student_ids": student_ids,
                            }
                        )

                    # Build list of sessions to end
                    to_end = []
                    for sid in list(all_active):
                        session_state = presence_svc.get_session_state(sid)
                        if not session_state:
                            if sid in pipeline_ids:
                                pass  # Let pipeline manage its own state
                            continue
                        schedule = session_state.schedule

                        # Only auto-end sessions that are "window-managed":
                        # started inside their natural (day, start..end) window.
                        # Sessions started manually outside the window (e.g.
                        # demo / restart on another day) must persist until
                        # they are ended explicitly — otherwise this job would
                        # end them within 15 s and the admin UI's "Start
                        # Session" button would appear to flap back after a
                        # successful click.
                        if not getattr(session_state, "auto_manage", True):
                            continue

                        # Safety: only auto-end on the session's own weekday.
                        # Without this guard a Monday schedule whose end_time
                        # is 10:00 would be auto-ended at 10:01 *any* day of
                        # the week, because the previous check was purely on
                        # time-of-day.
                        if schedule.day_of_week != current_day:
                            continue
                        if current_time <= schedule.end_time:
                            continue

                        # Fetch faculty_id and enrolled student_ids for notifications
                        faculty_id = str(schedule.faculty_id)
                        student_ids = [
                            str(e.student_id)
                            for e in db.query(Enrollment.student_id).filter(Enrollment.schedule_id == schedule.id).all()
                        ]

                        to_end.append(
                            {
                                "sid": sid,
                                "room_id": str(schedule.room_id),
                                "subject_code": schedule.subject_code,
                                "faculty_id": faculty_id,
                                "student_ids": student_ids,
                            }
                        )

                    return to_start, to_end
                finally:
                    db.close()

            try:
                to_start, to_end = await asyncio.to_thread(_gather_lifecycle_state)
            except Exception:
                logger.exception("[lifecycle] Session lifecycle check failed")
                return

            # --- Async phase: start/stop pipelines using gathered data ---

            # === Auto-start ===
            for info in to_start:
                sid = info["sid"]
                room_id = info["room_id"]
                camera_url = info["camera_url"]
                subject_code = info["subject_code"]
                faculty_id = info.get("faculty_id")
                student_ids = info.get("student_ids", [])

                try:
                    # Start legacy session (needs its own DB session)
                    db = SessionLocal()
                    try:
                        presence_svc = PresenceService(db)
                        await presence_svc.start_session(sid)
                    finally:
                        db.close()

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
                            faiss_manager.rebuild_user_map_from_db()
                        if not faiss_manager.user_map:
                            faiss_manager.rebuild_user_map_from_db()

                        # If a preview pipeline is running for this schedule
                        # (admin was watching it out-of-window), stop it before
                        # starting the full one so they don't fight over the
                        # same stream.
                        existing_preview = app.state.preview_pipelines.pop(sid, None)
                        if existing_preview is not None:
                            try:
                                await existing_preview.stop()
                                logger.info(
                                    "[lifecycle] Replaced preview with full pipeline for %s", sid
                                )
                            except Exception:
                                logger.exception(
                                    "[lifecycle] Failed to stop preview pipeline for %s", sid
                                )

                        pipeline = SessionPipeline(
                            schedule_id=sid,
                            grabber=grabber,
                            db_factory=SessionLocal,
                            room_id=room_id,
                        )
                        await pipeline.start()
                        app.state.session_pipelines[sid] = pipeline
                        logger.info(f"[lifecycle] Started pipeline for {subject_code} ({sid})")
                    else:
                        logger.warning(f"[lifecycle] No camera for {subject_code}, session started without pipeline")

                    # Send session-start notifications (fire-and-forget)
                    try:
                        from app.services.notification_service import notify as _notify
                        from app.services.notification_service import notify_many as _notify_many

                        db = SessionLocal()
                        try:
                            if faculty_id:
                                await _notify(
                                    db,
                                    faculty_id,
                                    "Session Started",
                                    f"{subject_code} session has started.",
                                    "session_start",
                                    toast_type="info",
                                    reference_id=str(sid),
                                    reference_type="schedule",
                                    # Suppress repeat "Session Started" for the
                                    # same schedule within 5 min — covers
                                    # pipeline self-heal restarts and back-to-back
                                    # 30-min rolling test sessions re-firing.
                                    dedup_window_seconds=300,
                                )
                            if student_ids:
                                await _notify_many(
                                    db,
                                    student_ids,
                                    "Class Started",
                                    f"{subject_code} is now in session.",
                                    "session_start",
                                    toast_type="info",
                                    reference_id=str(sid),
                                    reference_type="schedule",
                                    dedup_window_seconds=300,
                                )
                        finally:
                            db.close()
                    except Exception:
                        logger.warning(
                            f"[lifecycle] Session start notifications failed for {subject_code}",
                            exc_info=True,
                        )

                except Exception:
                    logger.exception(f"[lifecycle] Failed to start session {sid}")

            # === Auto-end ===
            for info in to_end:
                sid = info["sid"]
                room_id = info["room_id"]
                subject_code = info["subject_code"]
                faculty_id = info.get("faculty_id")
                student_ids = info.get("student_ids", [])

                try:
                    # Stop pipeline first
                    pipeline = app.state.session_pipelines.pop(sid, None)
                    if pipeline:
                        await pipeline.stop()
                        logger.info(f"[lifecycle] Stopped pipeline for {subject_code}")

                    # End legacy session
                    db = SessionLocal()
                    try:
                        presence_svc = PresenceService(db)
                        await presence_svc.end_session(sid)
                    finally:
                        db.close()
                    logger.info(f"[lifecycle] Ended session for {subject_code} ({sid})")

                    # Stop FrameGrabber — but only if no other active pipeline
                    # is still using the same room's grabber. This is the
                    # "seamless handoff" guard: back-to-back rolling sessions
                    # in the same classroom previously killed the grabber out
                    # from under the next pipeline, starving it of frames and
                    # leaving the UI stuck on "Detecting…".
                    frame_grabbers = app.state.frame_grabbers
                    still_used = any(
                        getattr(p, "room_id", None) == room_id
                        for p in app.state.session_pipelines.values()
                    )
                    if still_used:
                        logger.info(
                            f"[lifecycle] Keeping FrameGrabber for room {room_id} alive — "
                            f"next session already streaming"
                        )
                    elif room_id in frame_grabbers:
                        frame_grabbers[room_id].stop()
                        del frame_grabbers[room_id]
                        logger.info(f"[lifecycle] Stopped FrameGrabber for room {room_id}")

                    # Send session-end notifications (fire-and-forget)
                    try:
                        from app.services.notification_service import notify as _notify
                        from app.services.notification_service import notify_many as _notify_many

                        db = SessionLocal()
                        try:
                            if faculty_id:
                                await _notify(
                                    db,
                                    faculty_id,
                                    "Session Ended",
                                    f"{subject_code} session has ended.",
                                    "session_end",
                                    toast_type="info",
                                )
                            if student_ids:
                                await _notify_many(
                                    db,
                                    student_ids,
                                    "Class Ended",
                                    f"{subject_code} session has ended.",
                                    "session_end",
                                    toast_type="info",
                                )
                        finally:
                            db.close()
                    except Exception:
                        logger.warning(
                            f"[lifecycle] Session end notifications failed for {subject_code}",
                            exc_info=True,
                        )

                except Exception:
                    logger.exception(f"[lifecycle] Failed to end session {sid}")

        scheduler.add_job(
            run_session_lifecycle_check,
            "interval",
            seconds=15,
            id="session_lifecycle_check",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
            coalesce=True,
        )

        # ── Notification background jobs ──────────────────────────
        from app.services.notification_jobs import (
            run_anomaly_detection,
            run_daily_digest,
            run_low_attendance_check,
            run_notification_cleanup,
            run_weekly_digest,
        )

        scheduler.add_job(
            run_daily_digest,
            "cron",
            hour=settings.DAILY_DIGEST_HOUR,
            minute=0,
            id="daily_digest",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
        )

        scheduler.add_job(
            run_weekly_digest,
            "cron",
            day_of_week="sun",
            hour=settings.WEEKLY_DIGEST_HOUR,
            minute=0,
            id="weekly_digest",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
        )

        scheduler.add_job(
            run_low_attendance_check,
            "cron",
            hour=19,
            minute=15,
            id="low_attendance_check",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
        )

        scheduler.add_job(
            run_anomaly_detection,
            "cron",
            hour=20,
            minute=0,
            id="anomaly_detection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
        )

        scheduler.add_job(
            run_notification_cleanup,
            "cron",
            hour=3,
            minute=0,
            id="notification_cleanup",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
        )

        # Recognition-evidence retention (Phase G). Dry-run by default — the
        # operator flips RECOGNITION_EVIDENCE_RETENTION_DRY_RUN=false after
        # one sweep has logged the expected delete set. Hard cap inside the
        # job guards against config mistakes.
        if (
            settings.ENABLE_RECOGNITION_EVIDENCE
            and settings.ENABLE_RECOGNITION_EVIDENCE_RETENTION
        ):
            from app.services.recognition_retention import run_recognition_retention

            scheduler.add_job(
                run_recognition_retention,
                "cron",
                hour=3,
                minute=15,
                id="recognition_retention",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=3600,
                coalesce=True,
            )

        # Start the scheduler
        scheduler.start()
        logger.info(
            "APScheduler started — session lifecycle every 30s, FAISS health every 30m, "
            "daily digest at %02d:00, weekly digest Sun %02d:00, "
            "low-attendance check at 19:15, anomaly detection at 20:00, "
            "notification cleanup at 03:00",
            settings.DAILY_DIGEST_HOUR,
            settings.WEEKLY_DIGEST_HOUR,
        )

    except _SkipBackgroundJobs:
        logger.info("Background jobs disabled (ENABLE_BACKGROUND_JOBS=false) — skipping APScheduler")
    except Exception as e:
        logger.error(f"Failed to initialize APScheduler: {e}")

    logger.info(f"{settings.APP_NAME} startup complete")

    # ===================================================================
    # On-demand pipeline startup (called from WebSocket handler)
    # ===================================================================

    # Preview pipelines: lightweight, schedule-scoped SessionPipelines running
    # in preview_mode (no attendance side-effects). Keyed by schedule_id. These
    # exist ONLY while a WebSocket viewer is watching a schedule outside its
    # current time window, so they're torn down on the last viewer's disconnect
    # (see websocket.py's attendance_websocket.finally block).
    app.state.preview_pipelines = {}  # schedule_id -> SessionPipeline (preview_mode=True)

    async def ensure_pipeline_running(schedule_id: str) -> bool:
        """Start pipeline for a schedule if it should be active but isn't running.

        Called on WebSocket connect so faculty see bounding boxes immediately
        instead of waiting up to 30s for the next scheduler tick.

        Behaviour:
          1. If a full session pipeline is already running → return True.
          2. If the schedule is in its active window → start a full pipeline
             (creates attendance records, fires events).
          3. Otherwise → start a PREVIEW pipeline (detection + tracking + WS
             broadcast only, no DB writes) so the admin still sees bounding
             boxes on the live feed.

        Returns True if any pipeline (full or preview) is running for the
        schedule after this call.
        """
        # No-op when ML + frame grabbers are disabled (VPS thin profile).
        # WebSocket routes themselves are also disabled in that profile, so
        # this function shouldn't even be called — the guard is a belt-and-
        # braces against wiring mistakes.
        if not (settings.ENABLE_ML and settings.ENABLE_FRAME_GRABBERS):
            return False

        from datetime import datetime

        from app.models.room import Room
        from app.repositories.schedule_repository import ScheduleRepository
        from app.services.frame_grabber import FrameGrabber
        from app.services.realtime_pipeline import SessionPipeline

        # Already running a full pipeline?
        if schedule_id in app.state.session_pipelines:
            pipeline = app.state.session_pipelines[schedule_id]
            if pipeline.is_running:
                return True

        # Already running a preview pipeline?
        if schedule_id in app.state.preview_pipelines:
            pipeline = app.state.preview_pipelines[schedule_id]
            if pipeline.is_running:
                return True

        # Gather schedule + room info. Determine whether the schedule is in
        # its active window right now — this decides full vs preview mode.
        def _gather_info():
            db = SessionLocal()
            try:
                now = datetime.now()
                schedule_repo = ScheduleRepository(db)
                schedule = schedule_repo.get_by_id(schedule_id)
                if not schedule:
                    return None

                room = db.query(Room).filter(Room.id == schedule.room_id).first()
                camera_url = room.camera_endpoint if room else None
                room_id = str(schedule.room_id)

                current_day = now.weekday()
                current_time = now.time()
                in_window = (
                    current_day == schedule.day_of_week
                    and schedule.start_time <= current_time <= schedule.end_time
                )
                already_ended = PresenceService.was_session_ended_today(schedule_id)
                should_start_full = in_window and not already_ended

                return {
                    "sid": schedule_id,
                    "room_id": room_id,
                    "camera_url": camera_url,
                    "subject_code": schedule.subject_code,
                    "should_start_full": should_start_full,
                }
            finally:
                db.close()

        try:
            info = await asyncio.to_thread(_gather_info)
        except Exception:
            logger.exception("[on-demand] Failed to gather info for schedule %s", schedule_id)
            return False

        if info is None:
            return False

        sid = info["sid"]
        room_id = info["room_id"]
        camera_url = info["camera_url"]
        subject_code = info["subject_code"]
        should_start_full = info["should_start_full"]

        if not camera_url:
            logger.warning("[on-demand] No camera for %s (%s)", subject_code, sid)
            return False

        try:
            # Ensure FAISS index is hydrated before starting a tracker.
            from app.services.ml.faiss_manager import faiss_manager

            if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
                faiss_manager.load_or_create_index()
                faiss_manager.rebuild_user_map_from_db()
            if not faiss_manager.user_map:
                faiss_manager.rebuild_user_map_from_db()

            # Share FrameGrabbers across full + preview pipelines for the
            # same room — opening one RTSP reader is enough for the whole
            # stack (admin preview + attendance session both feed off it).
            if room_id not in app.state.frame_grabbers:
                app.state.frame_grabbers[room_id] = FrameGrabber(camera_url)
                logger.info("[on-demand] Created FrameGrabber for room %s", room_id)
            grabber = app.state.frame_grabbers[room_id]

            if should_start_full:
                # Start legacy session record first (so presence service has
                # something to bind to when the pipeline calls start_session).
                db = SessionLocal()
                try:
                    presence_svc = PresenceService(db)
                    await presence_svc.start_session(sid)
                finally:
                    db.close()

                # Swap any running preview for a full pipeline.
                existing_preview = app.state.preview_pipelines.pop(sid, None)
                if existing_preview is not None:
                    try:
                        await existing_preview.stop()
                        logger.info("[on-demand] Replaced preview with full pipeline for %s", sid)
                    except Exception:
                        logger.exception(
                            "[on-demand] Failed to stop preview pipeline for %s", sid
                        )

                pipeline = SessionPipeline(
                    schedule_id=sid,
                    grabber=grabber,
                    db_factory=SessionLocal,
                    room_id=room_id,
                    preview_mode=False,
                )
                await pipeline.start()
                app.state.session_pipelines[sid] = pipeline
                logger.info("[on-demand] Started FULL pipeline for %s (%s)", subject_code, sid)
                return True

            # Out-of-window admin viewer → preview pipeline only. Skips the
            # presence service, no attendance records, no session_start
            # notifications. Bounding boxes appear on the WS feed immediately.
            preview = SessionPipeline(
                schedule_id=sid,
                grabber=grabber,
                db_factory=SessionLocal,
                room_id=room_id,
                preview_mode=True,
            )
            await preview.start()
            app.state.preview_pipelines[sid] = preview
            logger.info("[on-demand] Started PREVIEW pipeline for %s (%s)", subject_code, sid)
            return True

        except Exception:
            logger.exception("[on-demand] Failed to start pipeline for %s", schedule_id)
            return False

    async def stop_preview_pipeline(schedule_id: str) -> bool:
        """Tear down a preview pipeline when the last WS viewer leaves.

        Called from websocket.py when `remove_attendance_client` drops the
        last client for a schedule. Leaves full pipelines untouched — those
        are owned by the lifecycle scheduler. Also tears down the room's
        FrameGrabber if nothing else is using it (no full or preview pipeline
        referencing the same room).
        """
        preview = app.state.preview_pipelines.pop(schedule_id, None)
        if preview is None:
            return False

        room_id = preview.room_id

        try:
            await preview.stop()
        except Exception:
            logger.exception("[on-demand] Failed to stop preview pipeline for %s", schedule_id)

        # Reap the FrameGrabber if no other pipeline (full or preview) in the
        # same room still needs it. Prevents keeping RTSP reader slots open
        # for a camera nobody's watching.
        if room_id and room_id in app.state.frame_grabbers:
            still_used = any(
                getattr(p, "room_id", None) == room_id
                for p in list(app.state.session_pipelines.values())
                + list(app.state.preview_pipelines.values())
            )
            if not still_used:
                try:
                    app.state.frame_grabbers[room_id].stop()
                finally:
                    app.state.frame_grabbers.pop(room_id, None)
                logger.info("[on-demand] Reaped idle FrameGrabber for room %s", room_id)

        logger.info("[on-demand] Stopped PREVIEW pipeline for schedule %s", schedule_id)
        return True

    # Expose to other modules via app.state
    app.state.ensure_pipeline_running = ensure_pipeline_running
    app.state.stop_preview_pipeline = stop_preview_pipeline

    # ===================================================================
    # YIELD — application serves requests
    # ===================================================================
    yield

    # ===================================================================
    # SHUTDOWN
    # ===================================================================
    logger.info(f"Shutting down {settings.APP_NAME}...")

    # Cancel FAISS subscriber task
    if hasattr(app.state, "faiss_subscriber_task"):
        app.state.faiss_subscriber_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.faiss_subscriber_task
        logger.info("FAISS subscriber task cancelled")

    # Stop APScheduler
    try:
        if scheduler.running:
            logger.info("Stopping APScheduler...")
            scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")

    # Stop all SessionPipelines (full + preview)
    if hasattr(app.state, "session_pipelines"):
        for sid, pipeline in list(app.state.session_pipelines.items()):
            try:
                await pipeline.stop()
                logger.info(f"SessionPipeline stopped for schedule {sid}")
            except Exception as e:
                logger.error(f"Failed to stop pipeline for schedule {sid}: {e}")
        app.state.session_pipelines.clear()

    if hasattr(app.state, "preview_pipelines"):
        for sid, pipeline in list(app.state.preview_pipelines.items()):
            try:
                await pipeline.stop()
                logger.info(f"Preview pipeline stopped for schedule {sid}")
            except Exception as e:
                logger.error(f"Failed to stop preview pipeline for schedule {sid}: {e}")
        app.state.preview_pipelines.clear()

    # Stop all FrameGrabbers
    if hasattr(app.state, "frame_grabbers"):
        for room_id, grabber in list(app.state.frame_grabbers.items()):
            try:
                grabber.stop()
                logger.info(f"FrameGrabber stopped for room {room_id}")
            except Exception as e:
                logger.error(f"Failed to stop FrameGrabber for room {room_id}: {e}")
        app.state.frame_grabbers.clear()

    # Stop recognition-evidence writer — drains at most a tiny final batch.
    try:
        from app.services.evidence_writer import evidence_writer

        await evidence_writer.stop()
    except Exception as e:
        logger.error(f"Failed to stop evidence writer: {e}")

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


# ===== FastAPI Application =====

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Attendance Monitoring System - Backend API",
    version="1.0.0",
    lifespan=lifespan,
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


# ===== Health Check =====

# Deep health check is registered below via health.router at /api/v1/health


@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint

    Returns a simple JSON response confirming the API is running.
    """
    return {"message": f"{settings.APP_NAME} API is running", "docs": f"{settings.API_PREFIX}/docs"}


# ===== Router Includes =====

API_PREFIX = settings.API_PREFIX

# Always-on routers. The faculty app needs auth + users + schedules + rooms;
# the student app and admin portal need those plus the feature-flagged ones
# below. Health is always on so the VPS LB / deploy scripts can probe.
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["Users"])
app.include_router(rooms.router, prefix=f"{API_PREFIX}/rooms", tags=["Rooms"])
app.include_router(schedules.router, prefix=f"{API_PREFIX}/schedules", tags=["Schedules"])
app.include_router(health.router, prefix=f"{API_PREFIX}/health", tags=["Health"])

# Feature-flagged routers. Each group is disabled in the VPS thin profile so
# the public-facing surface is minimal (no face embeddings / attendance data
# / student PII reachable).
_flagged_routers: list[tuple[bool, str, object, str, str]] = [
    (settings.ENABLE_FACE_ROUTES, "face", face.router, f"{API_PREFIX}/face", "Face"),
    (settings.ENABLE_ATTENDANCE_ROUTES, "attendance", attendance.router, f"{API_PREFIX}/attendance", "Attendance"),
    (settings.ENABLE_PRESENCE_ROUTES, "presence", presence.router, f"{API_PREFIX}/presence", "Presence"),
    (settings.ENABLE_ANALYTICS_ROUTES, "analytics", analytics.router, f"{API_PREFIX}/analytics", "Analytics"),
    (settings.ENABLE_NOTIFICATION_ROUTES, "notifications", notifications.router, f"{API_PREFIX}/notifications", "Notifications"),
    (settings.ENABLE_AUDIT_ROUTES, "audit", audit.router, f"{API_PREFIX}/audit", "Audit"),
    (settings.ENABLE_EDGE_ROUTES, "edge", edge_devices.router, f"{API_PREFIX}/edge", "Edge Devices"),
    (settings.ENABLE_SETTINGS_ROUTES, "settings", settings_router.router, f"{API_PREFIX}/settings", "Settings"),
    (settings.ENABLE_WS_ROUTES, "websocket", websocket.router, f"{API_PREFIX}/ws", "WebSocket"),
    (
        settings.ENABLE_RECOGNITION_ROUTES,
        "recognitions",
        recognitions.router,
        f"{API_PREFIX}/recognitions",
        "Recognition Evidence",
    ),
    (
        settings.ENABLE_ACTIVITY_ROUTES,
        "activity",
        activity.router,
        f"{API_PREFIX}/activity",
        "System Activity",
    ),
]

_enabled_names: list[str] = []
_disabled_names: list[str] = []
for enabled, name, router_obj, prefix, tag in _flagged_routers:
    if enabled:
        app.include_router(router_obj, prefix=prefix, tags=[tag])  # type: ignore[arg-type]
        _enabled_names.append(name)
    else:
        _disabled_names.append(name)

# One-line startup signal of the router profile — reviewers reading logs
# after a boot can confirm the thin profile actually skipped the heavy
# routers.
logger.info(
    "Routers: always-on=[auth,users,rooms,schedules,health] "
    "flagged-enabled=%s flagged-disabled=%s",
    _enabled_names,
    _disabled_names,
)


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
