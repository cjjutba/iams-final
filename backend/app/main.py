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

    # ── Health-notifier bootstrap ─────────────────────────────────
    # Capture the running event loop so daemon threads (FrameGrabber stderr
    # drain, etc.) can schedule notification coros via run_coroutine_threadsafe.
    # mark_boot() starts the 60s grace window so spurious deploy-time
    # transitions don't fire admin alerts.
    from app.services import health_notifier
    app.state.loop = asyncio.get_running_loop()
    health_notifier.mark_boot()

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
                await health_notifier.emit_one_shot(
                    title="FAISS reconciliation failed",
                    message=(
                        f"FAISS index reconciliation failed at startup: {e}. "
                        "Face recognition may be degraded."
                    ),
                    notification_type="faiss_reconcile_failed",
                    severity="critical",
                    preference_key="ml_health_alerts",
                    reference_id="faiss_reconcile",
                    reference_type="ml_index",
                    dedup_window_seconds=300,
                    toast_type="error",
                )

            # Background listener for FAISS reload notifications (multi-worker sync)
            app.state.faiss_subscriber_task = asyncio.create_task(faiss_manager.subscribe_index_changes())

            # Bootstrap auto-CCTV-enroller from DB so it stays one-shot
            # across restarts. Cheap (one aggregate query); flag-checked
            # so the work is skipped entirely when AUTO_CCTV_ENROLL_ENABLED
            # is false. Wrapped in try so a DB hiccup doesn't break boot.
            try:
                if settings.AUTO_CCTV_ENROLL_ENABLED:
                    from app.services.auto_cctv_enroller import auto_cctv_enroller
                    await asyncio.to_thread(auto_cctv_enroller.bootstrap_from_db)
            except Exception:
                logger.exception("AutoCctvEnroller bootstrap failed (non-fatal)")

            # JIT the SCRFD ONNX graph now so the first real session pipeline
            # doesn't pay the ~3-5s warmup tax on its first frame. (No-op if
            # the realtime path will route through the sidecar — but cheap
            # insurance against ML_SIDECAR_URL being unset later or the
            # registration path needing the in-process model.)
            await asyncio.to_thread(insightface_model.warmup)
            logger.info("InsightFace warmup complete")

            # Bind the realtime ML backend. ML_SIDECAR_URL set + reachable →
            # route SCRFD + ArcFace through the native macOS sidecar
            # (CoreML/ANE). Else use the in-process model. SessionPipeline
            # picks up whatever we bind here via app.services.ml.inference.
            from app.services.ml.inference import set_realtime_model

            sidecar_bound = False
            if settings.ML_SIDECAR_URL:
                try:
                    from app.services.ml.remote_insightface_model import (
                        RemoteInsightFaceModel,
                    )

                    remote = RemoteInsightFaceModel(settings.ML_SIDECAR_URL)
                    health = await asyncio.to_thread(remote.healthcheck)
                    if health and health.get("model_loaded"):
                        set_realtime_model(remote)
                        provider_summary = ", ".join(
                            f"{p['task']}={p['providers'][0] if p['providers'] else 'n/a'}"
                            for p in health.get("providers", [])
                        ) or "no providers reported"
                        logger.info(
                            "Realtime ML routed via sidecar at %s (%s)",
                            settings.ML_SIDECAR_URL,
                            provider_summary,
                        )
                        sidecar_bound = True
                        # Recovery transition fires only if the sidecar
                        # had previously been recorded as down.
                        await health_notifier.report_health(
                            resource="ml_sidecar",
                            is_healthy=True,
                            down_title="ML sidecar unavailable",
                            down_message=(
                                f"ML sidecar at {settings.ML_SIDECAR_URL} failed health probe "
                                "— using slower in-process inference"
                            ),
                            down_type="ml_sidecar_down",
                            recovered_title="ML sidecar recovered",
                            recovered_message="ML sidecar is responding again",
                            recovered_type="ml_sidecar_recovered",
                            preference_key="ml_health_alerts",
                            down_severity="warn",
                        )
                    else:
                        logger.warning(
                            "ML sidecar at %s did not pass health probe — "
                            "falling back to in-process inference",
                            settings.ML_SIDECAR_URL,
                        )
                        await health_notifier.report_health(
                            resource="ml_sidecar",
                            is_healthy=False,
                            down_title="ML sidecar unavailable",
                            down_message=(
                                f"ML sidecar at {settings.ML_SIDECAR_URL} failed health probe "
                                "— using slower in-process inference"
                            ),
                            down_type="ml_sidecar_down",
                            recovered_title="ML sidecar recovered",
                            recovered_message="ML sidecar is responding again",
                            recovered_type="ml_sidecar_recovered",
                            preference_key="ml_health_alerts",
                            down_severity="warn",
                        )
                        try:
                            remote.close()
                        except Exception:
                            pass
                except Exception:
                    logger.exception(
                        "Failed to initialise sidecar proxy — falling back to in-process"
                    )

            if not sidecar_bound:
                set_realtime_model(insightface_model)

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

    # Pre-open RTSP readers for every room with a configured camera so the
    # transition from "no session" → "session running" is instant. ML still
    # only runs when a SessionPipeline is attached (gated by the lifecycle
    # scheduler), but the grabber + decoder is already warm so the first
    # real frame lands in <1s instead of waiting for the FFmpeg I-frame
    # handshake. Skipped on the VPS thin profile where ENABLE_FRAME_GRABBERS
    # is false (no cameras reachable from the VPS network).
    if settings.ENABLE_ML and settings.ENABLE_FRAME_GRABBERS:
        try:
            from app.database import SessionLocal as _SessionLocal
            from app.models.room import Room as _Room
            from app.services.frame_grabber import FrameGrabber as _FrameGrabber

            _db = _SessionLocal()
            try:
                _rooms = (
                    _db.query(_Room)
                    .filter(_Room.camera_endpoint.isnot(None))
                    .filter(_Room.camera_endpoint != "")
                    .all()
                )
                for _room in _rooms:
                    _room_id = str(_room.id)
                    if _room_id in app.state.frame_grabbers:
                        continue
                    try:
                        app.state.frame_grabbers[_room_id] = _FrameGrabber(_room.camera_endpoint)
                        logger.info(
                            "FrameGrabber preloaded for room %s (%s)",
                            _room.name,
                            _room_id,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to preload FrameGrabber for room %s", _room_id
                        )
            finally:
                _db.close()
        except Exception:
            logger.exception("FrameGrabber preload phase failed")

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
                    await health_notifier.emit_one_shot(
                        title="FAISS index mismatch detected",
                        message=(
                            f"FAISS contains {faiss_count} vectors but DB has "
                            f"{active_count} active registrations"
                        ),
                        notification_type="faiss_mismatch",
                        severity="error",
                        preference_key="ml_health_alerts",
                        reference_id="faiss_mismatch",
                        reference_type="ml_index",
                        dedup_window_seconds=1800,
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

                        # Read from the SessionState's snapshotted primitives.
                        # session_state.schedule is the original ORM instance —
                        # its owning DB session has long since closed, so any
                        # attribute lazy-load (day_of_week, start_time,
                        # end_time, room_id, …) raises DetachedInstanceError
                        # and aborts this whole gather, which is how zombie
                        # sessions outlive their window. The snapshot fields
                        # below are plain Python primitives captured at
                        # SessionState.__init__ — safe to read forever.

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
                        if session_state.day_of_week != current_day:
                            continue
                        if current_time <= session_state.window_end:
                            continue

                        # Fetch enrolled student_ids for notifications.
                        # faculty_id comes from the snapshot; using `sid` for
                        # the enrollment query avoids touching the detached
                        # ORM instance entirely.
                        faculty_id = session_state.faculty_id
                        student_ids = [
                            str(e.student_id)
                            for e in db.query(Enrollment.student_id).filter(Enrollment.schedule_id == sid).all()
                        ]

                        to_end.append(
                            {
                                "sid": sid,
                                "room_id": session_state.room_id,
                                "subject_code": session_state.subject_code,
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

                    # FrameGrabbers are preloaded at boot for every room with a
                    # camera, but this fallback handles rooms added at runtime
                    # or a failed preload pass. Either way, ML detection only
                    # runs once a SessionPipeline is attached below.
                    if camera_url and room_id not in app.state.frame_grabbers:
                        grabber = FrameGrabber(camera_url)
                        app.state.frame_grabbers[room_id] = grabber
                        logger.info(f"[lifecycle] Created FrameGrabber for room {room_id}")

                    grabber = app.state.frame_grabbers.get(room_id)
                    if grabber:
                        # Self-heal FAISS before starting pipeline
                        from app.services.ml.faiss_manager import faiss_manager

                        if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
                            faiss_manager.load_or_create_index()
                            faiss_manager.rebuild_user_map_from_db()
                        if not faiss_manager.user_map:
                            faiss_manager.rebuild_user_map_from_db()

                        pipeline = SessionPipeline(
                            schedule_id=sid,
                            grabber=grabber,
                            db_factory=SessionLocal,
                            room_id=room_id,
                        )
                        await pipeline.start()
                        app.state.session_pipelines[sid] = pipeline
                        logger.info(f"[lifecycle] Started pipeline for {subject_code} ({sid})")

                        # System Activity event so the admin can see the
                        # ML pipeline coming online in the timeline.
                        # Fire-and-forget — never breaks the lifecycle loop.
                        try:
                            from app.services.activity_service import (
                                EventSeverity,
                                EventType,
                                emit_system_event,
                            )

                            db = SessionLocal()
                            try:
                                emit_system_event(
                                    db,
                                    event_type=EventType.PIPELINE_STARTED,
                                    summary=(
                                        f"Pipeline started for {subject_code}"
                                    ),
                                    severity=EventSeverity.SUCCESS,
                                    schedule_id=str(sid),
                                    room_id=str(room_id),
                                    payload={
                                        "subject_code": subject_code,
                                        "schedule_id": str(sid),
                                        "room_id": str(room_id),
                                    },
                                    autocommit=True,
                                )
                            finally:
                                db.close()
                        except Exception:
                            logger.warning(
                                "[lifecycle] PIPELINE_STARTED emit failed",
                                exc_info=True,
                            )
                    else:
                        logger.warning(f"[lifecycle] No camera for {subject_code}, session started without pipeline")
                        # Treat "session started but pipeline missing" as a
                        # WARN system event — the operator should know the
                        # camera was unavailable when the schedule fired.
                        try:
                            from app.services.activity_service import (
                                EventSeverity,
                                EventType,
                                emit_system_event,
                            )

                            db = SessionLocal()
                            try:
                                emit_system_event(
                                    db,
                                    event_type=EventType.CAMERA_OFFLINE,
                                    summary=(
                                        f"No camera available for {subject_code} — "
                                        f"session started without ML pipeline"
                                    ),
                                    severity=EventSeverity.WARN,
                                    schedule_id=str(sid),
                                    room_id=str(room_id),
                                    payload={
                                        "subject_code": subject_code,
                                        "schedule_id": str(sid),
                                        "room_id": str(room_id),
                                        "reason": "no_camera_endpoint_or_grabber",
                                    },
                                    autocommit=True,
                                )
                            finally:
                                db.close()
                        except Exception:
                            logger.warning(
                                "[lifecycle] CAMERA_OFFLINE emit failed",
                                exc_info=True,
                            )

                        # Admin-bell notification mirroring the system event.
                        # Dedup keyed on the room so back-to-back rolling
                        # sessions don't fan out duplicate alerts.
                        try:
                            await health_notifier.emit_one_shot(
                                title=f"Camera offline for {subject_code or room_id}",
                                message=(
                                    f"Session is starting in room {room_id} but no "
                                    f"camera is available — ML pipeline inactive"
                                ),
                                notification_type="camera_offline",
                                severity="error",
                                preference_key="camera_alerts",
                                reference_id=str(room_id),
                                reference_type="room",
                                dedup_window_seconds=600,
                            )
                        except Exception:
                            logger.warning(
                                "[lifecycle] camera_offline admin notify failed",
                                exc_info=True,
                            )

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

                        # System Activity event mirroring PIPELINE_STARTED so
                        # the admin sees the full lifecycle on the timeline.
                        try:
                            from app.services.activity_service import (
                                EventSeverity,
                                EventType,
                                emit_system_event,
                            )

                            db = SessionLocal()
                            try:
                                emit_system_event(
                                    db,
                                    event_type=EventType.PIPELINE_STOPPED,
                                    summary=(
                                        f"Pipeline stopped for {subject_code}"
                                    ),
                                    severity=EventSeverity.INFO,
                                    schedule_id=str(sid),
                                    room_id=str(room_id) if room_id else None,
                                    payload={
                                        "subject_code": subject_code,
                                        "schedule_id": str(sid),
                                        "room_id": str(room_id) if room_id else None,
                                    },
                                    autocommit=True,
                                )
                            finally:
                                db.close()
                        except Exception:
                            logger.warning(
                                "[lifecycle] PIPELINE_STOPPED emit failed",
                                exc_info=True,
                            )

                    # End legacy session
                    db = SessionLocal()
                    try:
                        presence_svc = PresenceService(db)
                        await presence_svc.end_session(sid)
                    finally:
                        db.close()
                    logger.info(f"[lifecycle] Ended session for {subject_code} ({sid})")

                    # FrameGrabbers stay alive for the lifetime of the process —
                    # the grabber + RTSP reader were preloaded at boot so the
                    # next session in this room transitions cleanly without a
                    # cold-start gap. Only the SessionPipeline (the ML attach)
                    # gets torn down here.

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

                    # Phase-5: marked_absent_session_end + session_zero_recognition
                    # ────────────────────────────────────────────────────────
                    # Once the auto-end has fired, look at today's attendance
                    # rows for this schedule. Anyone in the enrollment list
                    # without a row was never recognised — they get a personal
                    # "marked absent" notification. If NO rows exist at all
                    # for an enrolled class, that's an anomaly (camera /
                    # recognition pipeline issue) and faculty + admins get a
                    # session_zero_recognition alert. All of this is wrapped
                    # in its own try/except so a query failure here can't
                    # abort the lifecycle loop.
                    try:
                        from datetime import date as _date

                        from app.models.attendance_record import AttendanceRecord
                        from app.services.notification_service import (
                            notify as _notify_one,
                        )
                        from app.services.notification_service import notify_admins

                        session_date = _date.today()
                        session_date_str = session_date.isoformat()

                        db = SessionLocal()
                        try:
                            attendance_rows = (
                                db.query(AttendanceRecord)
                                .filter(
                                    AttendanceRecord.schedule_id == sid,
                                    AttendanceRecord.date == session_date,
                                )
                                .all()
                            )
                            present_ids = {
                                str(a.student_id) for a in attendance_rows
                            }
                            enrolled_id_set = {str(s) for s in student_ids}
                            absent_ids = enrolled_id_set - present_ids

                            # Per-student "you were marked absent" fan-out.
                            for student_id in absent_ids:
                                try:
                                    await _notify_one(
                                        db,
                                        student_id,
                                        f"Marked absent: {subject_code}",
                                        (
                                            f"You were marked absent for "
                                            f"{subject_code} on {session_date_str}."
                                        ),
                                        "marked_absent_session_end",
                                        severity="warn",
                                        preference_key="attendance_confirmation",
                                        send_email=False,
                                        dedup_window_seconds=0,
                                        reference_id=f"absent:{sid}:{session_date_str}",
                                        reference_type="attendance",
                                        toast_type="warning",
                                    )
                                except Exception:
                                    logger.debug(
                                        "[lifecycle] marked_absent_session_end "
                                        "notify failed for student %s",
                                        student_id,
                                        exc_info=True,
                                    )

                            # Zero-recognition guardrail: nobody got matched
                            # at all despite an enrolled class. Likely camera
                            # offline / ML pipeline missing — flag faculty +
                            # admins with email so it doesn't slip past.
                            if not attendance_rows and enrolled_id_set:
                                try:
                                    if faculty_id:
                                        await _notify_one(
                                            db,
                                            faculty_id,
                                            f"No attendance recorded: {subject_code}",
                                            (
                                                f"Session for {subject_code} "
                                                f"ended with zero recognized "
                                                f"check-ins despite "
                                                f"{len(enrolled_id_set)} "
                                                f"enrolled students. Camera or "
                                                f"recognition issue?"
                                            ),
                                            "session_zero_recognition",
                                            severity="warn",
                                            preference_key="anomaly_alerts",
                                            send_email=False,
                                            dedup_window_seconds=0,
                                            reference_id=f"zero_recog:{sid}:{session_date_str}",
                                            reference_type="schedule",
                                            toast_type="warning",
                                        )
                                except Exception:
                                    logger.debug(
                                        "[lifecycle] session_zero_recognition "
                                        "faculty notify failed",
                                        exc_info=True,
                                    )

                                try:
                                    await notify_admins(
                                        db,
                                        title=f"Zero recognition in {subject_code}",
                                        message=(
                                            f"Session ended with zero check-ins "
                                            f"(schedule {sid}). May indicate "
                                            f"camera or ML pipeline issue."
                                        ),
                                        notification_type="session_zero_recognition",
                                        severity="warn",
                                        preference_key="anomaly_alerts",
                                        send_email=True,
                                        dedup_window_seconds=0,
                                        reference_id=f"zero_recog:{sid}:{session_date_str}",
                                        reference_type="schedule",
                                        toast_type="warning",
                                    )
                                except Exception:
                                    logger.debug(
                                        "[lifecycle] session_zero_recognition "
                                        "admin notify failed",
                                        exc_info=True,
                                    )
                        finally:
                            db.close()
                    except Exception:
                        logger.warning(
                            "[lifecycle] marked_absent_session_end / "
                            "session_zero_recognition fan-out failed for %s",
                            subject_code,
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
            run_daily_health_summary,
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

        # Daily health summary at 06:00 UTC — admins only, opt-in via the
        # daily_health_summary preference (default off). Headline addition
        # of Phase 7: gives operators a single bell ping with camera /
        # recognition / error counts so silent regressions get noticed.
        scheduler.add_job(
            run_daily_health_summary,
            "cron",
            hour=6,
            minute=0,
            id="daily_health_summary",
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

    async def ensure_pipeline_running(schedule_id: str) -> bool:
        """Start the full session pipeline if the schedule's window is open.

        Strict session-gated policy: ML detection + recognition only run while
        a real session is active. Out-of-window WebSocket viewers see raw WHEP
        video with no overlays — no preview pipeline is spawned.

        Called on WebSocket connect to short-circuit the up-to-15s wait for the
        next ``session_lifecycle_check`` tick. Returns True iff a full pipeline
        is running for the schedule when this call returns.
        """
        # No-op when ML + frame grabbers are disabled (VPS thin profile).
        if not (settings.ENABLE_ML and settings.ENABLE_FRAME_GRABBERS):
            return False

        # Already running?
        if schedule_id in app.state.session_pipelines:
            pipeline = app.state.session_pipelines[schedule_id]
            if pipeline.is_running:
                return True

        from datetime import datetime

        from app.models.room import Room
        from app.repositories.schedule_repository import ScheduleRepository
        from app.services.frame_grabber import FrameGrabber
        from app.services.realtime_pipeline import SessionPipeline

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
                should_start = in_window and not already_ended

                return {
                    "sid": schedule_id,
                    "room_id": room_id,
                    "camera_url": camera_url,
                    "subject_code": schedule.subject_code,
                    "should_start": should_start,
                }
            finally:
                db.close()

        try:
            info = await asyncio.to_thread(_gather_info)
        except Exception:
            logger.exception("[on-demand] Failed to gather info for schedule %s", schedule_id)
            return False

        if info is None or not info["should_start"]:
            return False

        sid = info["sid"]
        room_id = info["room_id"]
        camera_url = info["camera_url"]
        subject_code = info["subject_code"]

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

            # FrameGrabbers are preloaded at boot; this fallback handles a
            # room added at runtime or a failed preload.
            if room_id not in app.state.frame_grabbers:
                app.state.frame_grabbers[room_id] = FrameGrabber(camera_url)
                logger.info("[on-demand] Created FrameGrabber for room %s", room_id)
            grabber = app.state.frame_grabbers[room_id]

            db = SessionLocal()
            try:
                presence_svc = PresenceService(db)
                await presence_svc.start_session(sid)
            finally:
                db.close()

            pipeline = SessionPipeline(
                schedule_id=sid,
                grabber=grabber,
                db_factory=SessionLocal,
                room_id=room_id,
            )
            await pipeline.start()
            app.state.session_pipelines[sid] = pipeline
            logger.info("[on-demand] Started pipeline for %s (%s)", subject_code, sid)
            return True

        except Exception:
            logger.exception("[on-demand] Failed to start pipeline for %s", schedule_id)
            return False

    # Expose to other modules via app.state
    app.state.ensure_pipeline_running = ensure_pipeline_running

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
