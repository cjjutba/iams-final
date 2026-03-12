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
    StudentAttendanceStatus,
    AttendanceUpdateRequest,
    AlertResponse,
    ScheduleAttendanceSummaryItem,
)
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services import session_manager
from app.utils.dependencies import get_current_user, get_current_student, get_current_faculty
from app.config import logger


router = APIRouter()


@router.get(
    "/schedule-summaries",
    response_model=List[ScheduleAttendanceSummaryItem],
    status_code=status.HTTP_200_OK,
)
def get_schedule_summaries(
    target_date: Optional[date] = Query(None, alias="date", description="Date to summarise (defaults to today)"),
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

    # Fetch all schedules this faculty teaches
    all_schedules = schedule_repo.get_by_faculty(str(current_user.id))

    # Filter to only those that occur on the requested day
    day_schedules = [s for s in all_schedules if s.day_of_week == day_of_week]

    results: List[ScheduleAttendanceSummaryItem] = []

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

        results.append(ScheduleAttendanceSummaryItem(
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
        ))

    # Sort by start_time
    results.sort(key=lambda x: x.start_time)

    return results


@router.get("/today", response_model=List[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_today_attendance(
    schedule_id: str = Query(..., description="Schedule UUID"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Get Today's Attendance** (Faculty Only)

    Get attendance records for all students in a schedule for today.

    - **schedule_id**: Schedule UUID (query parameter)

    Returns list of attendance records with student information.

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)
    today = date.today()

    records = attendance_repo.get_by_schedule_date(schedule_id, today)

    return [AttendanceRecordResponse.model_validate(r) for r in records]


@router.get("/today/{schedule_id}", response_model=List[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_today_attendance_by_path(
    schedule_id: str,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Get Today's Attendance by Schedule** (Faculty Only)

    Get attendance records for all students in a schedule for today.

    - **schedule_id**: Schedule UUID (path parameter)

    Returns list of attendance records with student information.

    Requires faculty authentication.
    """
    attendance_repo = AttendanceRepository(db)
    today = date.today()

    records = attendance_repo.get_by_schedule_date(schedule_id, today)

    return [AttendanceRecordResponse.model_validate(r) for r in records]


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

    return [AttendanceRecordResponse.model_validate(r) for r in records]


@router.get("/my-attendance", response_model=List[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_my_attendance_alias(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db)
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

    records = attendance_repo.get_student_history(
        str(current_user.id),
        start_date,
        end_date
    )

    return [AttendanceRecordResponse.model_validate(r) for r in records]


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


@router.get("/schedule/{schedule_id}", response_model=List[AttendanceRecordResponse], status_code=status.HTTP_200_OK)
def get_schedule_attendance(
    schedule_id: str,
    date: Optional[date] = Query(None, description="Specific date filter (defaults to today)"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
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

    return [AttendanceRecordResponse.model_validate(r) for r in records]


@router.get("/schedule/{schedule_id}/summary", response_model=dict, status_code=status.HTTP_200_OK)
def get_schedule_attendance_summary(
    schedule_id: str,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
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
    from app.repositories.schedule_repository import ScheduleRepository
    from app.models.attendance_record import AttendanceStatus

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
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "total_records": total_records,
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "excused_count": excused_count,
        "early_leave_count": early_leave_count,
        "attendance_rate": round(attendance_rate, 2)
    }


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
            student_number=getattr(record.student, 'student_id', None),
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


@router.get("/alerts", response_model=List[AlertResponse], status_code=status.HTTP_200_OK)
def get_early_leave_alerts(
    filter: Optional[str] = Query("all", description="Filter: today, week, or all"),
    schedule_id: Optional[str] = Query(None, description="Filter by schedule"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
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
    from fastapi import HTTPException

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
    events = attendance_repo.get_early_leave_events(
        schedule_id=schedule_id,
        start_date=start_date,
        end_date=end_date
    )

    # Build enriched response with student and schedule info
    alerts = []
    for event in events:
        attendance = attendance_repo.get_by_id(str(event.attendance_id))
        if not attendance:
            continue

        # Only show alerts for schedules this faculty teaches
        schedule = schedule_repo.get_by_id(str(attendance.schedule_id))
        if not schedule or str(schedule.faculty_id) != str(current_user.id):
            continue

        # Get student info
        student = db.query(User).filter(User.id == attendance.student_id).first()
        if not student:
            continue

        alerts.append(AlertResponse(
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
            date=attendance.date
        ))

    return alerts


@router.get("/export", status_code=status.HTTP_200_OK)
def export_attendance(
    schedule_id: str = Query(..., description="Schedule UUID"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    format: str = Query("csv", description="Export format: csv or json"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
):
    """
    **Export Attendance Report** (Faculty Only)

    Export attendance records for a schedule within a date range.

    - **schedule_id**: Schedule UUID
    - **start_date**: Start date
    - **end_date**: End date
    - **format**: Export format (csv or json)

    Returns attendance data in the requested format.

    Requires faculty authentication.
    """
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    import io
    import csv

    attendance_repo = AttendanceRepository(db)
    schedule_repo = ScheduleRepository(db)

    # Verify schedule exists and faculty owns it
    schedule = schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    if str(schedule.faculty_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only export attendance for your own schedules"
        )

    # Get all attendance records in range
    records = attendance_repo.get_by_schedule_date_range(schedule_id, start_date, end_date)

    if format == "csv":
        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Date", "Student ID", "Student Name", "Status",
            "Check In", "Check Out", "Presence Score",
            "Total Scans", "Scans Present", "Remarks"
        ])

        for record in records:
            student = db.query(User).filter(User.id == record.student_id).first()
            student_name = f"{student.first_name} {student.last_name}" if student else "Unknown"
            student_sid = student.student_id if student else "N/A"

            writer.writerow([
                record.date.isoformat(),
                student_sid,
                student_name,
                record.status.value if record.status else "unknown",
                record.check_in_time.isoformat() if record.check_in_time else "",
                record.check_out_time.isoformat() if record.check_out_time else "",
                record.presence_score,
                record.total_scans,
                record.scans_present,
                record.remarks or ""
            ])

        output.seek(0)
        filename = f"attendance_{schedule.subject_code}_{start_date}_{end_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    else:
        # JSON format
        result = []
        for record in records:
            student = db.query(User).filter(User.id == record.student_id).first()
            student_name = f"{student.first_name} {student.last_name}" if student else "Unknown"
            student_sid = student.student_id if student else "N/A"

            result.append({
                "date": record.date.isoformat(),
                "student_id": student_sid,
                "student_name": student_name,
                "status": record.status.value if record.status else "unknown",
                "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
                "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
                "presence_score": record.presence_score,
                "total_scans": record.total_scans,
                "scans_present": record.scans_present,
                "remarks": record.remarks
            })

        return {
            "schedule": {
                "id": str(schedule.id),
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name
            },
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_records": len(result),
            "records": result
        }


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

    return AttendanceRecordResponse.model_validate(record)


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

    return [PresenceLogResponse.model_validate(log) for log in logs]


@router.post("/manual-entry", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
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

    return AttendanceRecordResponse.model_validate(record)


@router.patch("/{attendance_id}", response_model=AttendanceRecordResponse, status_code=status.HTTP_200_OK)
def update_attendance_record(
    attendance_id: str,
    update_data: AttendanceUpdateRequest,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    record = attendance_repo.update(attendance_id, filtered_data)

    logger.info(f"Attendance record updated by {current_user.email}: {attendance_id}")

    return AttendanceRecordResponse.model_validate(record)


@router.get("/schedule-summaries", status_code=status.HTTP_200_OK)
def get_schedule_summaries(
    target_date: Optional[date] = Query(None, alias="date", description="Date to summarize (defaults to today)"),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    **Get Schedule Summaries** (Faculty Only)

    Get attendance summary for all of the faculty's schedules on a given date.
    Returns per-schedule present/late/absent/early_leave counts and rate.
    """
    from app.models.attendance_record import AttendanceStatus
    from app.models.schedule import Schedule
    from app.models.enrollment import Enrollment
    from sqlalchemy import func

    summary_date = target_date or date.today()

    # Get faculty's schedules
    schedules = db.query(Schedule).filter(
        Schedule.faculty_id == current_user.id
    ).all()

    results = []
    for schedule in schedules:
        from app.models.attendance_record import AttendanceRecord
        records = db.query(AttendanceRecord).filter(
            AttendanceRecord.schedule_id == schedule.id,
            AttendanceRecord.date == summary_date,
        ).all()

        enrolled = db.query(func.count(Enrollment.id)).filter(
            Enrollment.schedule_id == schedule.id
        ).scalar() or 0

        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        early_leave = sum(1 for r in records if r.status == AttendanceStatus.EARLY_LEAVE)
        total = len(records)
        rate = ((present + late) / total * 100.0) if total > 0 else 0.0

        results.append({
            "schedule_id": str(schedule.id),
            "subject_code": schedule.subject_code,
            "subject_name": schedule.subject_name,
            "start_time": str(schedule.start_time),
            "end_time": str(schedule.end_time),
            "room_name": schedule.room.name if schedule.room else None,
            "total_enrolled": enrolled,
            "present_count": present,
            "late_count": late,
            "absent_count": absent,
            "early_leave_count": early_leave,
            "attendance_rate": round(rate, 1),
            "session_active": session_manager.is_session_active(str(schedule.id)),
        })

    return results


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

    return [EarlyLeaveResponse.model_validate(event) for event in events]
