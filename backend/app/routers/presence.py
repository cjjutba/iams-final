"""
Presence Tracking API Router

Endpoints for continuous presence monitoring, scan logs, and early-leave events.

Key Features:
- Get presence logs for an attendance record
- Get early-leave events
- Session management (start/end sessions)
- Real-time tracking statistics
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import logger
from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.attendance import EarlyLeaveEventResponse, PresenceLogResponse
from app.services.presence_service import PresenceService
from app.utils.dependencies import get_current_user
from app.utils.exceptions import NotFoundError

router = APIRouter()


# ===== Schemas =====


class SessionStartRequest(BaseModel):
    schedule_id: str


class SessionEndRequest(BaseModel):
    schedule_id: str


class SessionStartResponse(BaseModel):
    schedule_id: str
    started_at: datetime
    student_count: int
    message: str


class SessionEndResponse(BaseModel):
    schedule_id: str
    total_scans: int
    total_students: int
    present_count: int
    early_leave_count: int
    message: str


class ActiveSessionsResponse(BaseModel):
    active_sessions: list[str]
    count: int


class RoomStatusResponse(BaseModel):
    active: bool
    schedule_id: str | None = None


# ===== Session Management Endpoints =====


@router.post(
    "/sessions/start",
    response_model=SessionStartResponse,
    summary="Start Attendance Session",
    description="Start a new attendance tracking session for a schedule",
)
async def start_session(
    body: SessionStartRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start attendance session

    Creates attendance records for all enrolled students and initializes
    tracking session for continuous presence monitoring.
    Also auto-starts the video analytics pipeline for the room.

    Requires: Faculty or Admin role
    """
    # Check permissions - only faculty/admin can start sessions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only faculty and admins can start sessions")

    try:
        presence_service = PresenceService(db)
        session_state = await presence_service.start_session(body.schedule_id)

        # Start FrameGrabber for attendance engine scans
        # (FrameGrabber is also auto-created by the scan cycle if missing)
        schedule = ScheduleRepository(db).get_by_id(body.schedule_id)
        if schedule:
            room_id = str(schedule.room_id)
            frame_grabbers = getattr(http_request.app.state, "frame_grabbers", None)
            if frame_grabbers is not None and room_id not in frame_grabbers:
                from app.models.room import Room

                room = db.query(Room).filter(Room.id == schedule.room_id).first()
                camera_url = room.camera_endpoint if room else None
                if camera_url:
                    try:
                        from app.services.frame_grabber import FrameGrabber

                        grabber = FrameGrabber(camera_url)
                        frame_grabbers[room_id] = grabber
                        logger.info(f"FrameGrabber started for room {room_id}")
                    except Exception as fg_err:
                        logger.error(f"Failed to start FrameGrabber for room {room_id}: {fg_err}")

            # Start real-time SessionPipeline for face detection → attendance
            session_pipelines = getattr(http_request.app.state, "session_pipelines", None)
            if session_pipelines is not None and body.schedule_id not in session_pipelines:
                grabber = frame_grabbers.get(room_id) if frame_grabbers else None
                if grabber:
                    try:
                        from app.services.ml.faiss_manager import faiss_manager

                        if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
                            faiss_manager.load_or_create_index()
                            faiss_manager.rebuild_user_map_from_db()
                        if not faiss_manager.user_map:
                            faiss_manager.rebuild_user_map_from_db()

                        # If an admin was watching this schedule out-of-window,
                        # a preview pipeline is currently running. Stop it
                        # before starting the full one so they don't compete
                        # for the same grabber.
                        preview_pipelines = getattr(http_request.app.state, "preview_pipelines", None)
                        if preview_pipelines is not None:
                            existing_preview = preview_pipelines.pop(body.schedule_id, None)
                            if existing_preview is not None:
                                try:
                                    await existing_preview.stop()
                                    logger.info(
                                        f"Replaced preview with full pipeline for {body.schedule_id}"
                                    )
                                except Exception as prev_err:
                                    logger.error(f"Failed to stop preview pipeline: {prev_err}")

                        from app.database import SessionLocal
                        from app.services.realtime_pipeline import SessionPipeline

                        pipeline = SessionPipeline(
                            schedule_id=body.schedule_id,
                            grabber=grabber,
                            db_factory=SessionLocal,
                            room_id=room_id,
                        )
                        await pipeline.start()
                        session_pipelines[body.schedule_id] = pipeline
                        logger.info(f"SessionPipeline started for schedule {body.schedule_id}")
                    except Exception as pipe_err:
                        logger.error(f"Failed to start SessionPipeline: {pipe_err}")

        return SessionStartResponse(
            schedule_id=session_state.schedule_id,
            started_at=session_state.start_time,
            student_count=len(session_state.student_states),
            message=f"Session started with {len(session_state.student_states)} students",
        )

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start session: {str(e)}"
        ) from e


@router.post(
    "/sessions/end",
    response_model=SessionEndResponse,
    summary="End Attendance Session",
    description="End an active attendance tracking session",
)
async def end_session(
    body: SessionEndRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    End attendance session

    Finalizes presence scores, stops tracking, and stops the video pipeline.

    Requires: Faculty or Admin role
    """
    # Check permissions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only faculty and admins can end sessions")

    schedule_id = body.schedule_id

    try:
        presence_service = PresenceService(db)

        # Get session state before ending
        session_state = presence_service.get_session_state(schedule_id)
        if not session_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"No active session for schedule {schedule_id}"
            )

        # End session
        await presence_service.end_session(schedule_id)

        # Stop SessionPipeline if running
        session_pipelines = getattr(http_request.app.state, "session_pipelines", None)
        if session_pipelines is not None and schedule_id in session_pipelines:
            try:
                pipeline = session_pipelines.pop(schedule_id)
                await pipeline.stop()
                logger.info(f"SessionPipeline stopped for schedule {schedule_id}")
            except Exception as pipe_err:
                logger.error(f"Failed to stop SessionPipeline: {pipe_err}")

        # Stop FrameGrabber and clear identity cache for this room
        schedule = ScheduleRepository(db).get_by_id(schedule_id)
        if schedule:
            room_id = str(schedule.room_id)
            frame_grabbers = getattr(http_request.app.state, "frame_grabbers", None)
            if frame_grabbers and room_id in frame_grabbers:
                try:
                    frame_grabbers[room_id].stop()
                    del frame_grabbers[room_id]
                    logger.info(f"FrameGrabber stopped for room {room_id}")
                except Exception as fg_err:
                    logger.error(f"Failed to stop FrameGrabber for room {room_id}: {fg_err}")

            # Clear identity cache for this session
            try:
                from app.redis_client import get_redis
                from app.services.identity_cache import IdentityCache

                redis_client = await get_redis()
                cache = IdentityCache(redis_client)
                await cache.clear_session(room_id, schedule_id)
                logger.info(f"Identity cache cleared for room {room_id}, schedule {schedule_id}")
            except Exception as cache_err:
                logger.error(f"Failed to clear identity cache: {cache_err}")

        # Build summary
        return SessionEndResponse(
            schedule_id=schedule_id,
            total_scans=session_state.scan_count,
            total_students=len(session_state.student_states),
            present_count=sum(1 for s in session_state.student_states.values() if not s.get("early_leave_flagged")),
            early_leave_count=sum(1 for s in session_state.student_states.values() if s.get("early_leave_flagged")),
            message="Session ended successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to end session: {str(e)}"
        ) from e


@router.get(
    "/sessions/active",
    response_model=ActiveSessionsResponse,
    summary="Get Active Sessions",
    description="Get list of currently active attendance sessions",
)
async def get_active_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get active sessions

    Returns list of schedule IDs with active attendance tracking.

    Requires: Faculty or Admin role
    """
    # Check permissions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only faculty and admins can view sessions")

    try:
        presence_service = PresenceService(db)
        active_sessions = presence_service.get_active_sessions()

        return ActiveSessionsResponse(active_sessions=active_sessions, count=len(active_sessions))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get active sessions: {str(e)}"
        ) from e


# ===== Room Status Endpoint (for Edge Device) =====


@router.get(
    "/sessions/room-status",
    response_model=RoomStatusResponse,
    summary="Check Room Session Status",
    description="Check if there is an active session for a given room. Used by edge devices.",
)
async def get_room_session_status(room_id: str = Query(..., description="Room UUID"), db: Session = Depends(get_db)):
    """
    Check if a room has an active attendance session.

    Used by the Raspberry Pi edge device to decide whether to scan.
    No authentication required (edge devices use this on trusted network).
    """
    try:
        presence_service = PresenceService(db)
        schedule_repo = ScheduleRepository(db)

        # Check all active sessions and find one matching this room
        active_session_ids = presence_service.get_active_sessions()

        for schedule_id in active_session_ids:
            schedule = schedule_repo.get_by_id(schedule_id)
            if schedule and str(schedule.room_id) == room_id:
                return RoomStatusResponse(active=True, schedule_id=schedule_id)

        return RoomStatusResponse(active=False, schedule_id=None)

    except Exception as e:
        logger.error(f"Failed to check room status: {e}")
        return RoomStatusResponse(active=False, schedule_id=None)


# ===== Presence Log Endpoints =====


@router.get(
    "/{attendance_id}/logs",
    response_model=list[PresenceLogResponse],
    summary="Get Presence Logs",
    description="Get all presence scan logs for an attendance record",
)
async def get_presence_logs(
    attendance_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get presence logs

    Returns all scan logs for a specific attendance record.

    Access:
    - Students can view their own logs
    - Faculty can view logs for their classes
    - Admins can view all logs
    """
    try:
        attendance_repo = AttendanceRepository(db)

        # Get attendance record
        attendance = attendance_repo.get_by_id(attendance_id)
        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Attendance record not found: {attendance_id}"
            )

        # Check permissions
        if current_user.role == UserRole.STUDENT:
            # Students can only view their own logs
            if str(attendance.student_id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own attendance logs"
                )
        elif current_user.role == UserRole.FACULTY:
            # Faculty can only view logs for their own classes
            schedule_repo = ScheduleRepository(db)
            schedule = schedule_repo.get_by_id(str(attendance.schedule_id))
            if schedule and str(schedule.faculty_id) != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this schedule")

        # Get presence logs
        logs = attendance_repo.get_presence_logs(attendance_id)

        return [
            PresenceLogResponse(
                id=log.id,
                attendance_id=str(log.attendance_id),
                scan_number=log.scan_number,
                scan_time=log.scan_time,
                detected=log.detected,
                confidence=log.confidence,
            )
            for log in logs
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get presence logs: {str(e)}"
        ) from e


# ===== Early Leave Event Endpoints =====


@router.get(
    "/early-leaves",
    response_model=list[EarlyLeaveEventResponse],
    summary="Get Early Leave Events",
    description="Get early leave events with optional filters",
)
async def get_early_leave_events(
    schedule_id: str | None = Query(None, description="Filter by schedule"),
    start_date: date | None = Query(None, description="Filter by start date"),
    end_date: date | None = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get early leave events

    Returns list of early leave events with optional filters.

    Access:
    - Faculty can view events for their classes
    - Admins can view all events
    - Students cannot access this endpoint
    """
    # Check permissions
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students cannot access early leave reports")

    try:
        attendance_repo = AttendanceRepository(db)

        # Get early leave events
        events = attendance_repo.get_early_leave_events(
            schedule_id=schedule_id, start_date=start_date, end_date=end_date
        )

        return [
            EarlyLeaveEventResponse(
                id=str(event.id),
                attendance_id=str(event.attendance_id),
                detected_at=event.detected_at,
                last_seen_at=event.last_seen_at,
                consecutive_misses=event.consecutive_misses,
                notified=event.notified,
                notified_at=event.notified_at,
            )
            for event in events
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get early leave events: {str(e)}"
        ) from e
