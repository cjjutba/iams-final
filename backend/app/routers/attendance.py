"""
Attendance Router

API endpoints for attendance tracking and management.
Includes live attendance monitoring for continuous presence tracking.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.config import logger
from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.attendance import (
    AlertResponse,
    AttendanceRecordResponse,
    AttendanceSummary,
    AttendanceUpdateRequest,
    LiveAttendanceResponse,
    ManualAttendanceRequest,
    PresenceLogResponse,
    ScheduleAttendanceSummaryItem,
    StudentAttendanceStatus,
)
from app.services import session_manager
from app.utils.dependencies import get_current_faculty, get_current_student, get_current_user

router = APIRouter()


def _enrich(record) -> AttendanceRecordResponse:
    """Build AttendanceRecordResponse with student_name and subject_code populated."""
    resp = AttendanceRecordResponse.model_validate(record)
    if hasattr(record, "student") and record.student:
        resp.student_name = f"{record.student.first_name} {record.student.last_name}"
    if hasattr(record, "schedule") and record.schedule:
        resp.subject_code = record.schedule.subject_code
    return resp


@router.get("", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def list_attendance_records(
    student_id: str | None = Query(None, description="Filter by student UUID"),
    schedule_id: str | None = Query(None, description="Filter by schedule UUID"),
    start_date: date | None = Query(None, description="Start date filter"),
    end_date: date | None = Query(None, description="End date filter"),
    status_filter: str | None = Query(None, alias="status", description="Filter by attendance status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **List Attendance Records** (Admin/Faculty)

    General-purpose attendance listing with filters.
    Admins see all records; faculty see records for their schedules;
    students see only their own records.
    """
    import uuid as _uuid

    from sqlalchemy.orm import joinedload

    from app.models.attendance_record import AttendanceRecord as AR
    from app.models.attendance_record import AttendanceStatus as AStatus

    query = db.query(AR).options(joinedload(AR.student), joinedload(AR.schedule))

    # Role-based scoping
    if current_user.role == UserRole.STUDENT:
        query = query.filter(AR.student_id == current_user.id)
    elif current_user.role == UserRole.FACULTY:
        from app.models.schedule import Schedule

        query = query.join(Schedule, AR.schedule_id == Schedule.id).filter(Schedule.faculty_id == current_user.id)

    # Optional filters
    if student_id:
        query = query.filter(AR.student_id == _uuid.UUID(student_id))
    if schedule_id:
        query = query.filter(AR.schedule_id == _uuid.UUID(schedule_id))
    if start_date:
        query = query.filter(AR.date >= start_date)
    if end_date:
        query = query.filter(AR.date <= end_date)
    if status_filter:
        try:
            query = query.filter(AR.status == AStatus(status_filter))
        except ValueError:
            pass  # ignore unknown status

    records = query.order_by(AR.date.desc()).offset(skip).limit(limit).all()

    return [_enrich(r) for r in records]


@router.get(
    "/schedule-summaries",
    response_model=list[ScheduleAttendanceSummaryItem],
    status_code=status.HTTP_200_OK,
)
def get_schedule_summaries(
    target_date: date | None = Query(None, alias="date", description="Date to summarise (defaults to today)"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Get Attendance Summaries Per Schedule** (Faculty Only)

    Returns per-schedule attendance summaries for all classes the faculty
    teaches on the given date (or today if omitted). Each item contains
    present/late/absent counts, attendance rate, session status, and
    schedule metadata.

    Requires faculty authentication.
    """
    from app.models.attendance_record import AttendanceStatus as DBAttendanceStatus

    schedule_repo = ScheduleRepository(db)
    attendance_repo = AttendanceRepository(db)

    summary_date = target_date if target_date else date.today()

    # Get the day_of_week for the target date (Monday=0 ... Sunday=6)
    day_of_week = summary_date.weekday()

    # Admin sees all schedules; faculty sees only their own
    if current_user.role == UserRole.ADMIN:
        all_schedules = schedule_repo.get_all()
    else:
        all_schedules = schedule_repo.get_by_faculty(str(current_user.id))

    # Filter to only those that occur on the requested day
    day_schedules = [s for s in all_schedules if s.day_of_week == day_of_week]

    results: list[ScheduleAttendanceSummaryItem] = []

    for schedule in day_schedules:
        schedule_id = str(schedule.id)

        # Get attendance records for this schedule on the target date
        records = attendance_repo.get_by_schedule_date(schedule_id, summary_date)

        # Count by status
        present_count = sum(1 for r in records if r.status == DBAttendanceStatus.PRESENT)
        late_count = sum(1 for r in records if r.status == DBAttendanceStatus.LATE)
        absent_count = sum(1 for r in records if r.status == DBAttendanceStatus.ABSENT)

        # Get enrolled students for total
        enrolled_students = schedule_repo.get_enrolled_students(schedule_id)
        total_enrolled = len(enrolled_students)

        # Calculate attendance rate
        attendance_rate = 0.0
        if total_enrolled > 0:
            attendance_rate = ((present_count + late_count) / total_enrolled) * 100

        # Check session status
        is_active = session_manager.is_session_active(schedule_id)

        # Room name
        room_name = schedule.room.name if schedule.room else None

        results.append(
            ScheduleAttendanceSummaryItem(
                schedule_id=schedule_id,
                subject_code=schedule.subject_code,
                subject_name=schedule.subject_name,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                room_name=room_name,
                session_active=is_active,
                total_enrolled=total_enrolled,
                present_count=present_count,
                late_count=late_count,
                absent_count=absent_count,
                attendance_rate=round(attendance_rate, 2),
            )
        )

    # Sort by start_time
    results.sort(key=lambda x: x.start_time)

    return results


@router.get("/today", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_today_attendance(
    schedule_id: str = Query(..., description="Schedule UUID"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Get Today's Attendance** (Faculty Only)

    Get attendance records for all students in a schedule for today.

    - **schedule_id**: Schedule UUID (query parameter)

    Returns list of attendance records with student information.

    Requires faculty authentication.
    """
    # Faculty schedule ownership check (admins bypass)
    if current_user.role == UserRole.FACULTY:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)
        if not schedule:
            from fastapi import HTTPException

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
        if str(schedule.faculty_id) != str(current_user.id):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this schedule's attendance"
            )

    attendance_repo = AttendanceRepository(db)
    today = date.today()

    records = attendance_repo.get_by_schedule_date(schedule_id, today)

    return [_enrich(r) for r in records]


@router.get("/today/{schedule_id}", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_today_attendance_by_path(
    schedule_id: str, current_user: User = Depends(get_current_faculty), db: Session = Depends(get_db)
):
    """
    **Get Today's Attendance by Schedule** (Faculty Only)

    Get attendance records for all students in a schedule for today.

    - **schedule_id**: Schedule UUID (path parameter)

    Returns list of attendance records with student information.

    Requires faculty authentication.
    """
    # Faculty schedule ownership check (admins bypass)
    if current_user.role == UserRole.FACULTY:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)
        if not schedule:
            from fastapi import HTTPException

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
        if str(schedule.faculty_id) != str(current_user.id):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this schedule's attendance"
            )

    attendance_repo = AttendanceRepository(db)
    today = date.today()

    records = attendance_repo.get_by_schedule_date(schedule_id, today)

    return [_enrich(r) for r in records]


@router.get("/me", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_my_attendance(
    start_date: date | None = Query(None, description="Start date filter"),
    end_date: date | None = Query(None, description="End date filter"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
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

    records = attendance_repo.get_student_history(str(current_user.id), start_date, end_date)

    return [_enrich(r) for r in records]


@router.get("/my-attendance", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_my_attendance_alias(
    start_date: date | None = Query(None, description="Start date filter"),
    end_date: date | None = Query(None, description="End date filter"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    **Get My Attendance History** (Student Only) - Alias endpoint

    Get attendance history for the current student.

    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter

    Returns attendance records sorted by date (most recent first).

    Requires student authentication.

    Note: This is an alias for /me endpoint for backward compatibility.
    """
    attendance_repo = AttendanceRepository(db)

    records = attendance_repo.get_student_history(str(current_user.id), start_date, end_date)

    return [_enrich(r) for r in records]


@router.get("/me/summary", response_model=AttendanceSummary, status_code=status.HTTP_200_OK)
def get_my_attendance_summary(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
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

    summary = attendance_repo.get_summary(str(current_user.id), start_date, end_date)

    return AttendanceSummary(**summary)


@router.get("/schedule/{schedule_id}", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_schedule_attendance(
    schedule_id: str,
    date: date | None = Query(None, description="Specific date filter (defaults to today)"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Get Schedule Attendance** (Faculty Only)

    Get attendance records for a schedule on a specific date.

    - **schedule_id**: Schedule UUID
    - **date**: Specific date (defaults to today)

    Returns list of attendance records with student information.

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)
    attendance_date = date if date else datetime.now().date()

    records = attendance_repo.get_by_schedule_date(schedule_id, attendance_date)

    return [_enrich(r) for r in records]


@router.get("/schedule/{schedule_id}/summary", response_model=dict, status_code=status.HTTP_200_OK)
def get_schedule_attendance_summary(
    schedule_id: str,
    start_date: date | None = Query(None, description="Start date"),
    end_date: date | None = Query(None, description="End date"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Get Schedule Attendance Summary** (Faculty Only)

    Get attendance summary statistics for a schedule.

    - **schedule_id**: Schedule UUID
    - **start_date**: Optional start date (defaults to semester start)
    - **end_date**: Optional end date (defaults to today)

    Returns summary with attendance counts and rates.

    Requires faculty authentication.
    """
    from app.models.attendance_record import AttendanceStatus
    from app.repositories.schedule_repository import ScheduleRepository

    attendance_repo = AttendanceRepository(db)
    schedule_repo = ScheduleRepository(db)

    # Verify schedule exists
    schedule = schedule_repo.get_by_id(schedule_id)
    if not schedule:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    # Default date range
    if not start_date:
        start_date = datetime.now().date().replace(month=8, day=1)  # Default to August 1
    if not end_date:
        end_date = datetime.now().date()

    # Get all records in range
    records = attendance_repo.get_by_schedule_date_range(schedule_id, start_date, end_date)

    # Calculate statistics
    total_records = len(records)
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
    early_leave_count = sum(1 for r in records if r.status == AttendanceStatus.EARLY_LEAVE)

    attendance_rate = 0.0
    if total_records > 0:
        attendance_rate = ((present_count + late_count) / total_records) * 100

    return {
        "schedule_id": schedule_id,
        "subject_code": schedule.subject_code,
        "subject_name": schedule.subject_name,
        "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "total_records": total_records,
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "excused_count": excused_count,
        "early_leave_count": early_leave_count,
        "attendance_rate": round(attendance_rate, 2),
    }


@router.get("/live/{schedule_id}", response_model=LiveAttendanceResponse, status_code=status.HTTP_200_OK)
async def get_live_attendance(
    schedule_id: str, current_user: User = Depends(get_current_faculty), db: Session = Depends(get_db)
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
        student_statuses.append(
            StudentAttendanceStatus(
                student_id=str(record.student_id),
                student_number=getattr(record.student, "student_id", None),
                student_name=f"{record.student.first_name} {record.student.last_name}",
                status=record.status,
                check_in_time=record.check_in_time,
                presence_score=record.presence_score,
                total_scans=record.total_scans,
                scans_present=record.scans_present,
            )
        )

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
        students=student_statuses,
    )


@router.get("/alerts", response_model=list[AlertResponse], status_code=status.HTTP_200_OK)
def get_early_leave_alerts(
    filter: str | None = Query("all", description="Filter: today, week, or all"),
    schedule_id: str | None = Query(None, description="Filter by schedule"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Get Early Leave Alerts** (Faculty Only)

    Get early leave alerts for the faculty's schedules.

    - **filter**: Time filter (today, week, all)
    - **schedule_id**: Optional schedule filter

    Returns list of early leave alerts with student and schedule details.

    Requires faculty authentication.
    """
    from datetime import timedelta

    attendance_repo = AttendanceRepository(db)
    schedule_repo = ScheduleRepository(db)

    # Determine date range based on filter
    start_date = None
    end_date = None
    today_date = date.today()

    if filter == "today":
        start_date = today_date
        end_date = today_date
    elif filter == "week":
        # Start of current week (Monday)
        start_date = today_date - timedelta(days=today_date.weekday())
        end_date = today_date

    # Get early leave events
    events = attendance_repo.get_early_leave_events(schedule_id=schedule_id, start_date=start_date, end_date=end_date)

    # Build enriched response with student and schedule info
    alerts = []
    for event in events:
        attendance = attendance_repo.get_by_id(str(event.attendance_id))
        if not attendance:
            continue

        # Admin sees all alerts; faculty sees only their own schedules
        schedule = schedule_repo.get_by_id(str(attendance.schedule_id))
        if not schedule:
            continue
        if current_user.role != UserRole.ADMIN and str(schedule.faculty_id) != str(current_user.id):
            continue

        # Get student info
        student = db.query(User).filter(User.id == attendance.student_id).first()
        if not student:
            continue

        alerts.append(
            AlertResponse(
                id=str(event.id),
                attendance_id=str(event.attendance_id),
                student_id=str(student.id),
                student_name=f"{student.first_name} {student.last_name}",
                student_student_id=student.student_id,
                schedule_id=str(attendance.schedule_id),
                subject_code=schedule.subject_code,
                subject_name=schedule.subject_name,
                detected_at=event.detected_at,
                last_seen_at=event.last_seen_at,
                consecutive_misses=event.consecutive_misses,
                notified=event.notified,
                date=attendance.date,
                returned=event.returned,
                returned_at=event.returned_at,
                absence_duration_seconds=event.absence_duration_seconds,
            )
        )

    # Sort: still-absent first (more urgent), then by detected_at descending
    alerts.sort(key=lambda a: (a.returned, -(a.detected_at.timestamp() if a.detected_at else 0)))
    return alerts


@router.get("/export", status_code=status.HTTP_200_OK)
def export_attendance(
    schedule_id: str | None = Query(None, description="Schedule UUID (optional for admins)"),
    start_date: date | None = Query(None, description="Start date"),
    end_date: date | None = Query(None, description="End date"),
    status_filter: str | None = Query(None, alias="status", description="Filter by attendance status"),
    format: str = Query("csv", description="Export format: csv or json"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Export Attendance Report**

    Export attendance records with optional filters.
    Admins can export all records; faculty can only export their own schedules.

    Returns attendance data in the requested format.
    """
    import csv
    import io

    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from sqlalchemy.orm import joinedload

    from app.models.attendance_record import AttendanceRecord as AR
    from app.models.attendance_record import AttendanceStatus as AStatus

    query = db.query(AR).options(joinedload(AR.student), joinedload(AR.schedule))

    # Role-based scoping
    if current_user.role == UserRole.FACULTY:
        from app.models.schedule import Schedule

        if schedule_id:
            schedule_repo = ScheduleRepository(db)
            schedule = schedule_repo.get_by_id(schedule_id)
            if not schedule:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
            if str(schedule.faculty_id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only export attendance for your own schedules",
                )
            query = query.filter(AR.schedule_id == schedule.id)
        else:
            query = query.join(Schedule, AR.schedule_id == Schedule.id).filter(Schedule.faculty_id == current_user.id)
    elif current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students cannot export attendance")
    else:
        # Admin — optionally filter by schedule
        if schedule_id:
            import uuid as _uuid

            query = query.filter(AR.schedule_id == _uuid.UUID(schedule_id))

    # Apply filters
    if start_date:
        query = query.filter(AR.date >= start_date)
    if end_date:
        query = query.filter(AR.date <= end_date)
    if status_filter:
        try:
            query = query.filter(AR.status == AStatus(status_filter))
        except ValueError:
            pass

    records = query.order_by(AR.date.desc()).limit(5000).all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Date",
                "Student ID",
                "Student Name",
                "Subject",
                "Status",
                "Check In",
                "Check Out",
                "Presence Score",
                "Total Scans",
                "Scans Present",
                "Remarks",
            ]
        )

        for record in records:
            student_name = f"{record.student.first_name} {record.student.last_name}" if record.student else "Unknown"
            student_sid = record.student.student_id if record.student else "N/A"
            subject = record.schedule.subject_code if record.schedule else "N/A"

            writer.writerow(
                [
                    record.date.isoformat(),
                    student_sid,
                    student_name,
                    subject,
                    record.status.value if record.status else "unknown",
                    record.check_in_time.isoformat() if record.check_in_time else "",
                    record.check_out_time.isoformat() if record.check_out_time else "",
                    record.presence_score,
                    record.total_scans,
                    record.scans_present,
                    record.remarks or "",
                ]
            )

        output.seek(0)
        date_suffix = f"_{start_date}_{end_date}" if start_date and end_date else f"_{date.today()}"
        filename = f"attendance_export{date_suffix}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    else:
        result = []
        for record in records:
            student_name = f"{record.student.first_name} {record.student.last_name}" if record.student else "Unknown"
            student_sid = record.student.student_id if record.student else "N/A"
            subject = record.schedule.subject_code if record.schedule else "N/A"

            result.append(
                {
                    "date": record.date.isoformat(),
                    "student_id": student_sid,
                    "student_name": student_name,
                    "subject": subject,
                    "status": record.status.value if record.status else "unknown",
                    "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
                    "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
                    "presence_score": record.presence_score,
                    "total_scans": record.total_scans,
                    "scans_present": record.scans_present,
                    "remarks": record.remarks,
                }
            )

        return {
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "total_records": len(result),
            "records": result,
        }


@router.get("/export/pdf", status_code=status.HTTP_200_OK)
def export_attendance_pdf(
    schedule_ids: str = Query(..., description="Comma-separated schedule UUIDs, or 'all'"),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Export Attendance Report as PDF** (Faculty/Admin)

    Generates a detailed PDF attendance report for the specified schedules
    and date range.

    - **schedule_ids**: Comma-separated schedule UUIDs, or "all" for all faculty schedules
    - **start_date**: Start date (inclusive)
    - **end_date**: End date (inclusive)

    Returns a PDF file as a streaming response.

    Requires faculty or admin authentication.
    """
    import uuid as _uuid

    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from sqlalchemy import and_
    from sqlalchemy.orm import joinedload

    from app.models.attendance_record import AttendanceRecord as AR
    from app.models.attendance_record import AttendanceStatus as AStatus
    from app.services.pdf_service import generate_attendance_pdf

    schedule_repo = ScheduleRepository(db)

    def _get_records_with_students(schedule_id: str, sd: date, ed: date) -> list:
        """Fetch attendance records with eager-loaded student relationships."""
        return (
            db.query(AR)
            .options(joinedload(AR.student))
            .filter(
                and_(
                    AR.schedule_id == _uuid.UUID(schedule_id),
                    AR.date >= sd,
                    AR.date <= ed,
                )
            )
            .order_by(AR.date.desc())
            .all()
        )

    # Resolve schedules
    if schedule_ids.strip().lower() == "all":
        if current_user.role == UserRole.ADMIN:
            schedules = schedule_repo.get_all(limit=10000)
        else:
            schedules = schedule_repo.get_by_faculty(str(current_user.id))
    else:
        raw_ids = [sid.strip() for sid in schedule_ids.split(",") if sid.strip()]
        schedules = []
        for sid in raw_ids:
            try:
                _uuid.UUID(sid)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid schedule UUID: {sid}",
                )
            schedule = schedule_repo.get_by_id(sid)
            if not schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schedule not found: {sid}",
                )
            # Faculty can only export their own schedules
            if current_user.role == UserRole.FACULTY and str(schedule.faculty_id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to export schedule: {sid}",
                )
            schedules.append(schedule)

    if not schedules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No schedules found",
        )

    # Build class sections data for the PDF
    class_sections = []
    for schedule in schedules:
        records = _get_records_with_students(str(schedule.id), start_date, end_date)

        # Compute summary
        total_records = len(records)
        present_count = sum(1 for r in records if r.status == AStatus.PRESENT)
        late_count = sum(1 for r in records if r.status == AStatus.LATE)
        absent_count = sum(1 for r in records if r.status == AStatus.ABSENT)
        early_leave_count = sum(1 for r in records if r.status == AStatus.EARLY_LEAVE)
        attendance_rate = 0.0
        if total_records > 0:
            attendance_rate = ((present_count + late_count) / total_records) * 100

        # Build record dicts
        record_dicts = []
        for r in records:
            student_name = f"{r.student.first_name} {r.student.last_name}" if r.student else "Unknown"
            student_number = r.student.student_id if r.student else "N/A"
            record_dicts.append(
                {
                    "date": r.date,
                    "student_name": student_name,
                    "student_number": student_number,
                    "status": r.status,
                    "check_in_time": r.check_in_time,
                    "presence_score": r.presence_score,
                }
            )

        room_name = schedule.room.name if schedule.room else "N/A"

        class_sections.append(
            {
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "room_name": room_name,
                "summary": {
                    "total_records": total_records,
                    "present_count": present_count,
                    "late_count": late_count,
                    "absent_count": absent_count,
                    "early_leave_count": early_leave_count,
                    "attendance_rate": round(attendance_rate, 2),
                },
                "records": record_dicts,
            }
        )

    # Generate PDF
    faculty_name = f"{current_user.first_name} {current_user.last_name}"
    pdf_bytes = generate_attendance_pdf(faculty_name, start_date, end_date, class_sections)

    date_suffix = f"_{start_date}_{end_date}"
    filename = f"attendance_report{date_suffix}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/early-leaves", response_model=list[AlertResponse], status_code=status.HTTP_200_OK)
def get_early_leave_events(
    schedule_id: str | None = Query(None, description="Filter by schedule"),
    start_date: date | None = Query(None, description="Start date filter"),
    end_date: date | None = Query(None, description="End date filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get Early Leave Events**

    Get list of early leave events with optional filters, enriched with student and schedule info.

    - **schedule_id**: Optional schedule filter
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter

    Returns list of early leave events sorted by detection time.
    """
    attendance_repo = AttendanceRepository(db)
    schedule_repo = ScheduleRepository(db)

    events = attendance_repo.get_early_leave_events(schedule_id, start_date, end_date)

    alerts = []
    for event in events:
        attendance = attendance_repo.get_by_id(str(event.attendance_id))
        if not attendance:
            continue

        schedule = schedule_repo.get_by_id(str(attendance.schedule_id))
        if not schedule:
            continue

        student = db.query(User).filter(User.id == attendance.student_id).first()
        if not student:
            continue

        alerts.append(
            AlertResponse(
                id=str(event.id),
                attendance_id=str(event.attendance_id),
                student_id=str(student.id),
                student_name=f"{student.first_name} {student.last_name}",
                student_student_id=student.student_id,
                schedule_id=str(attendance.schedule_id),
                subject_code=schedule.subject_code,
                subject_name=schedule.subject_name,
                detected_at=event.detected_at,
                last_seen_at=event.last_seen_at,
                consecutive_misses=event.consecutive_misses,
                notified=event.notified,
                date=attendance.date,
                returned=event.returned,
                returned_at=event.returned_at,
                absence_duration_seconds=event.absence_duration_seconds,
            )
        )

    return alerts


@router.get("/{attendance_id}", response_model=AttendanceRecordResponse, status_code=status.HTTP_200_OK)
def get_attendance_record(
    attendance_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
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

    return _enrich(record)


@router.get("/{attendance_id}/logs", response_model=list[PresenceLogResponse], status_code=status.HTTP_200_OK)
def get_presence_logs(
    attendance_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
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

    return [PresenceLogResponse.model_validate(log) for log in logs]


@router.post("/manual-entry", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
def manual_attendance_entry(
    request: ManualAttendanceRequest, current_user: User = Depends(get_current_faculty), db: Session = Depends(get_db)
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
    existing = attendance_repo.get_by_student_date(request.student_id, request.schedule_id, request.date)

    if existing:
        # Update existing record
        record = attendance_repo.update(str(existing.id), {"status": request.status, "remarks": request.remarks})
        logger.info(f"Attendance updated manually by {current_user.email}: {existing.id}")
    else:
        # Create new record
        record = attendance_repo.create(
            {
                "student_id": request.student_id,
                "schedule_id": request.schedule_id,
                "date": request.date,
                "status": request.status,
                "remarks": request.remarks,
            }
        )
        logger.info(f"Attendance created manually by {current_user.email}: {record.id}")

    return _enrich(record)


@router.patch("/{attendance_id}", response_model=AttendanceRecordResponse, status_code=status.HTTP_200_OK)
def update_attendance_record(
    attendance_id: str,
    update_data: AttendanceUpdateRequest,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Update Attendance Record** (Faculty Only)

    Update attendance record fields.

    Allowed fields: status, remarks

    - **attendance_id**: Attendance record UUID
    - **status**: New attendance status (optional)
    - **remarks**: Notes or comments (optional)

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)

    # Filter out None values
    filtered_data = {k: v for k, v in update_data.model_dump().items() if v is not None}

    if not filtered_data:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    record = attendance_repo.update(attendance_id, filtered_data)

    logger.info(f"Attendance record updated by {current_user.email}: {attendance_id}")

    return _enrich(record)
