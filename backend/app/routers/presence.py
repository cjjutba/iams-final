"""
Presence Tracking API Router

Endpoints for continuous presence monitoring, scan logs, and early-leave events.

Key Features:
- Get presence logs for an attendance record
- Get early-leave events
- Session management (start/end sessions)
- Real-time tracking statistics
"""

from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.config import logger
from app.database import get_db
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.presence_service import PresenceService
from app.services.tracking_service import get_tracking_service
from app.services.session_scheduler import mark_manually_ended
from app.utils.dependencies import get_current_user
from app.utils.exceptions import NotFoundError
from app.models.user import User, UserRole
from app.schemas.attendance import PresenceLogResponse, EarlyLeaveEventResponse
from pydantic import BaseModel

router = APIRouter()


# ===== Schemas =====

class SessionStartRequest(BaseModel):
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


class TrackingStatsResponse(BaseModel):
    schedule_id: str
    total_tracks: int
    confirmed_tracks: int
    identified_tracks: int
    unidentified_tracks: int


class ActiveSessionsResponse(BaseModel):
    active_sessions: List[str]
    count: int


class RoomStatusResponse(BaseModel):
    active: bool
    schedule_id: Optional[str] = None


# ===== Session Management Endpoints =====

@router.post(
    "/sessions/start",
    response_model=SessionStartResponse,
    summary="Start Attendance Session",
    description="Start a new attendance tracking session for a schedule"
)
async def start_session(
    request: SessionStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start attendance session

    Creates attendance records for all enrolled students and initializes
    tracking session for continuous presence monitoring.

    Requires: Faculty or Admin role
    """
    # Check permissions - only faculty/admin can start sessions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admins can start sessions"
        )

    try:
        presence_service = PresenceService(db)
        session_state = await presence_service.start_session(request.schedule_id)

        return SessionStartResponse(
            schedule_id=session_state.schedule_id,
            started_at=session_state.start_time,
            student_count=len(session_state.student_states),
            message=f"Session started with {len(session_state.student_states)} students"
        )

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )


@router.post(
    "/sessions/end",
    response_model=SessionEndResponse,
    summary="End Attendance Session",
    description="End an active attendance tracking session"
)
async def end_session(
    schedule_id: str = Query(..., description="Schedule UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    End attendance session

    Finalizes presence scores and stops tracking for the session.

    Requires: Faculty or Admin role
    """
    # Check permissions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admins can end sessions"
        )

    try:
        presence_service = PresenceService(db)

        # Get session state before ending
        session_state = presence_service.get_session_state(schedule_id)
        if not session_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active session for schedule {schedule_id}"
            )

        # End session
        await presence_service.end_session(schedule_id)

        # Mark as manually ended so auto-scheduler won't restart
        mark_manually_ended(schedule_id)

        # Build summary
        return SessionEndResponse(
            schedule_id=schedule_id,
            total_scans=session_state.scan_count,
            total_students=len(session_state.student_states),
            present_count=sum(
                1 for s in session_state.student_states.values()
                if not s.get("early_leave_flagged")
            ),
            early_leave_count=sum(
                1 for s in session_state.student_states.values()
                if s.get("early_leave_flagged")
            ),
            message="Session ended successfully"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to end session: {str(e)}"
        )


@router.get(
    "/sessions/active",
    response_model=ActiveSessionsResponse,
    summary="Get Active Sessions",
    description="Get list of currently active attendance sessions"
)
async def get_active_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get active sessions

    Returns list of schedule IDs with active attendance tracking.

    Requires: Faculty or Admin role
    """
    # Check permissions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admins can view sessions"
        )

    try:
        presence_service = PresenceService(db)
        active_sessions = presence_service.get_active_sessions()

        return ActiveSessionsResponse(
            active_sessions=active_sessions,
            count=len(active_sessions)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active sessions: {str(e)}"
        )


# ===== Room Status Endpoint (for Edge Device) =====

@router.get(
    "/sessions/room-status",
    response_model=RoomStatusResponse,
    summary="Check Room Session Status",
    description="Check if there is an active session for a given room. Used by edge devices."
)
async def get_room_session_status(
    room_id: str = Query(..., description="Room UUID"),
    db: Session = Depends(get_db)
):
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
    response_model=List[PresenceLogResponse],
    summary="Get Presence Logs",
    description="Get all presence scan logs for an attendance record"
)
async def get_presence_logs(
    attendance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attendance record not found: {attendance_id}"
            )

        # Check permissions
        if current_user.role == UserRole.STUDENT:
            # Students can only view their own logs
            if str(attendance.student_id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own attendance logs"
                )
        elif current_user.role == UserRole.FACULTY:
            # Faculty can view logs for their classes
            # TODO: Add check that current_user is faculty for this schedule
            pass

        # Get presence logs
        logs = attendance_repo.get_presence_logs(attendance_id)

        return [
            PresenceLogResponse(
                id=log.id,
                attendance_id=str(log.attendance_id),
                scan_number=log.scan_number,
                scan_time=log.scan_time,
                detected=log.detected,
                confidence=log.confidence
            )
            for log in logs
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get presence logs: {str(e)}"
        )


# ===== Early Leave Event Endpoints =====

@router.get(
    "/early-leaves",
    response_model=List[EarlyLeaveEventResponse],
    summary="Get Early Leave Events",
    description="Get early leave events with optional filters"
)
async def get_early_leave_events(
    schedule_id: Optional[str] = Query(None, description="Filter by schedule"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot access early leave reports"
        )

    try:
        attendance_repo = AttendanceRepository(db)

        # Get early leave events
        events = attendance_repo.get_early_leave_events(
            schedule_id=schedule_id,
            start_date=start_date,
            end_date=end_date
        )

        return [
            EarlyLeaveEventResponse(
                id=str(event.id),
                attendance_id=str(event.attendance_id),
                detected_at=event.detected_at,
                last_seen_at=event.last_seen_at,
                consecutive_misses=event.consecutive_misses,
                notified=event.notified,
                notified_at=event.notified_at
            )
            for event in events
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get early leave events: {str(e)}"
        )


# ===== Tracking Statistics Endpoints =====

@router.get(
    "/tracking/stats/{schedule_id}",
    response_model=TrackingStatsResponse,
    summary="Get Tracking Statistics",
    description="Get real-time tracking statistics for a session"
)
async def get_tracking_stats(
    schedule_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get tracking stats

    Returns real-time tracking statistics including active tracks,
    confirmed tracks, and identified users.

    Requires: Faculty or Admin role
    """
    # Check permissions
    if current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admins can view tracking stats"
        )

    try:
        tracking_service = get_tracking_service()
        stats = tracking_service.get_session_stats(schedule_id)

        return TrackingStatsResponse(
            schedule_id=schedule_id,
            **stats
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracking stats: {str(e)}"
        )
