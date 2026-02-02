"""
Attendance Router

API endpoints for attendance tracking and management.
Includes live attendance monitoring for continuous presence tracking.
"""

from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.attendance import (
    ManualAttendanceRequest,
    AttendanceRecordResponse,
    AttendanceSummary,
    PresenceLogResponse,
    EarlyLeaveResponse,
    LiveAttendanceResponse,
    StudentAttendanceStatus
)
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services import session_manager
from app.utils.dependencies import get_current_user, get_current_student, get_current_faculty
from app.config import logger


router = APIRouter()


@router.get("/today", response_model=List[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_today_attendance(
    schedule_id: str = Query(..., description="Schedule UUID"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Get Today's Attendance** (Faculty Only)

    Get attendance records for all students in a schedule for today.

    - **schedule_id**: Schedule UUID

    Returns list of attendance records with student information.

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)
    today = date.today()

    records = attendance_repo.get_by_schedule_date(schedule_id, today)

    return [AttendanceRecordResponse.from_orm(r) for r in records]


@router.get("/me", response_model=List[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_my_attendance(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    **Get My Attendance History** (Student Only)

    Get attendance history for the current student.

    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter

    Returns attendance records sorted by date (most recent first).

    Requires student authentication.
    """
    attendance_repo = AttendanceRepository(db)

    records = attendance_repo.get_student_history(
        str(current_user.id),
        start_date,
        end_date
    )

    return [AttendanceRecordResponse.from_orm(r) for r in records]


@router.get("/me/summary", response_model=AttendanceSummary, status_code=status.HTTP_200_OK)
def get_my_attendance_summary(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    **Get My Attendance Summary** (Student Only)

    Get attendance statistics for a date range.

    - **start_date**: Start date
    - **end_date**: End date

    Returns attendance summary with counts and attendance rate.

    Requires student authentication.
    """
    attendance_repo = AttendanceRepository(db)

    summary = attendance_repo.get_summary(
        str(current_user.id),
        start_date,
        end_date
    )

    return AttendanceSummary(**summary)


@router.get("/live/{schedule_id}", response_model=LiveAttendanceResponse, status_code=status.HTTP_200_OK)
async def get_live_attendance(
    schedule_id: str,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Get Live Attendance Status** (Faculty Only)

    Get real-time attendance status for a class session.

    Shows:
    - Overall statistics (present, late, absent, early leave)
    - Individual student status with presence scores
    - Current scan results

    - **schedule_id**: Schedule UUID

    **Note:** This endpoint provides current session state.
    For real-time updates, use WebSocket (`/ws/{user_id}`).

    Requires faculty authentication.
    """
    schedule_repo = ScheduleRepository(db)
    attendance_repo = AttendanceRepository(db)

    # Get schedule
    schedule = schedule_repo.get_by_id(schedule_id)
    if not schedule:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    # Get today's attendance
    today = date.today()
    records = attendance_repo.get_by_schedule_date(schedule_id, today)

    # Get enrolled students count
    enrolled_students = schedule_repo.get_enrolled_students(schedule_id)
    total_enrolled = len(enrolled_students)

    # Build student status list
    student_statuses = []
    present_count = 0
    late_count = 0
    absent_count = 0
    early_leave_count = 0

    for record in records:
        student_statuses.append(StudentAttendanceStatus(
            student_id=str(record.student_id),
            student_name=f"{record.student.first_name} {record.student.last_name}",
            status=record.status,
            check_in_time=record.check_in_time,
            presence_score=record.presence_score,
            total_scans=record.total_scans,
            scans_present=record.scans_present
        ))

        # Update counts
        from app.models.attendance_record import AttendanceStatus
        if record.status == AttendanceStatus.PRESENT:
            present_count += 1
        elif record.status == AttendanceStatus.LATE:
            late_count += 1
        elif record.status == AttendanceStatus.ABSENT:
            absent_count += 1
        elif record.status == AttendanceStatus.EARLY_LEAVE:
            early_leave_count += 1

    # Check if session is currently active using global session manager
    session_active = session_manager.is_session_active(schedule_id)

    return LiveAttendanceResponse(
        schedule_id=schedule_id,
        subject_code=schedule.subject_code,
        subject_name=schedule.subject_name,
        date=today,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        session_active=session_active,
        total_enrolled=total_enrolled,
        present_count=present_count,
        late_count=late_count,
        absent_count=absent_count,
        early_leave_count=early_leave_count,
        students=student_statuses
    )


@router.get("/{attendance_id}", response_model=AttendanceRecordResponse, status_code=status.HTTP_200_OK)
def get_attendance_record(
    attendance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Get Attendance Record by ID**

    Retrieve detailed attendance record.

    - **attendance_id**: Attendance record UUID

    Students can only view their own records.
    Faculty can view records for their schedules.

    Requires authentication.
    """
    attendance_repo = AttendanceRepository(db)
    record = attendance_repo.get_by_id(attendance_id)

    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

    # Permission check
    if current_user.role == UserRole.STUDENT and str(record.student_id) != str(current_user.id):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return AttendanceRecordResponse.from_orm(record)


@router.get("/{attendance_id}/logs", response_model=List[PresenceLogResponse], status_code=status.HTTP_200_OK)
def get_presence_logs(
    attendance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Get Presence Logs**

    Get all presence scan logs for an attendance record.

    Shows individual scan results (detected/not detected) throughout the class.

    - **attendance_id**: Attendance record UUID

    Requires authentication (with appropriate permissions).
    """
    attendance_repo = AttendanceRepository(db)

    # Check if record exists and user has permission
    record = attendance_repo.get_by_id(attendance_id)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

    if current_user.role == UserRole.STUDENT and str(record.student_id) != str(current_user.id):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Get presence logs
    logs = attendance_repo.get_presence_logs(attendance_id)

    return [PresenceLogResponse.from_orm(log) for log in logs]


@router.post("/manual", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
def manual_attendance_entry(
    request: ManualAttendanceRequest,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Manual Attendance Entry** (Faculty Only)

    Manually create or update attendance record.

    Useful for:
    - Correcting automated attendance
    - Marking attendance when system is unavailable
    - Excused absences

    - **student_id**: Student UUID
    - **schedule_id**: Schedule UUID
    - **date**: Attendance date
    - **status**: Attendance status
    - **remarks**: Optional remarks

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)

    # Check if record already exists
    existing = attendance_repo.get_by_student_date(
        request.student_id,
        request.schedule_id,
        request.date
    )

    if existing:
        # Update existing record
        record = attendance_repo.update(str(existing.id), {
            "status": request.status,
            "remarks": request.remarks
        })
        logger.info(f"Attendance updated manually by {current_user.email}: {existing.id}")
    else:
        # Create new record
        record = attendance_repo.create({
            "student_id": request.student_id,
            "schedule_id": request.schedule_id,
            "date": request.date,
            "status": request.status,
            "remarks": request.remarks
        })
        logger.info(f"Attendance created manually by {current_user.email}: {record.id}")

    return AttendanceRecordResponse.from_orm(record)


@router.patch("/{attendance_id}", response_model=AttendanceRecordResponse, status_code=status.HTTP_200_OK)
def update_attendance_record(
    attendance_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Update Attendance Record** (Faculty Only)

    Update attendance record fields.

    Allowed fields: status, remarks

    - **attendance_id**: Attendance record UUID
    - **update_data**: Fields to update

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)

    # Only allow certain fields to be updated
    allowed_fields = ["status", "remarks"]
    filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    record = attendance_repo.update(attendance_id, filtered_data)

    logger.info(f"Attendance record updated by {current_user.email}: {attendance_id}")

    return AttendanceRecordResponse.from_orm(record)


@router.get("/early-leaves/", response_model=List[EarlyLeaveResponse], status_code=status.HTTP_200_OK)
def get_early_leave_events(
    schedule_id: Optional[str] = Query(None, description="Filter by schedule"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Get Early Leave Events** (Faculty Only)

    Get list of early leave events with optional filters.

    - **schedule_id**: Optional schedule filter
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter

    Returns list of early leave events sorted by detection time.

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)

    events = attendance_repo.get_early_leave_events(schedule_id, start_date, end_date)

    return [EarlyLeaveResponse.from_orm(event) for event in events]
