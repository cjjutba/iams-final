"""
Schedules Router

API endpoints for class schedule management.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import logger
from app.database import get_db
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.enrollment import Enrollment
from app.models.face_registration import FaceRegistration
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import (
    ScheduleConfigUpdate,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    ScheduleWithStudents,
    SessionSummary,
)
from app.services import session_manager
from app.utils.dependencies import get_current_user, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Runtime status derivation
#
# `Schedule.is_active` is the enable/archive flag — it does NOT change with
# the clock. The admin "Schedule Management" page used to show "Active" for
# every enabled row, which read as "session is running" to operators. To
# fix that, we compute a presentation-only `runtime_status` per row using
# session_manager (which schedule IDs have a running pipeline?) plus the
# current wall clock (is this schedule's window in the past, present, or
# future?).
#
# Status taxonomy (frontend renders one badge per value):
#   "live"      — register_session() has been called for this schedule.id
#   "upcoming"  — today is the schedule's day, current time is before window
#   "ended"     — today, current time is past the window's end
#   "scheduled" — any other day (the common case for most rows)
#   "disabled"  — schedule.is_active is False (operator-archived)
#
# The "in window today but not live" gap (15 s lifecycle tick hasn't fired
# yet) collapses into "live" optimistically — see lessons file 2026-04-25.
# ---------------------------------------------------------------------------


def _compute_runtime_status(
    schedule: Schedule,
    active_session_ids: set[str],
    now: datetime,
) -> str:
    if not schedule.is_active:
        return "disabled"
    if str(schedule.id) in active_session_ids:
        return "live"
    if schedule.day_of_week != now.weekday():
        return "scheduled"
    now_t = now.time()
    if now_t < schedule.start_time:
        return "upcoming"
    if now_t > schedule.end_time:
        return "ended"
    # Today, in window, not registered — the lifecycle scheduler ticks every
    # 15 s and will register it shortly. Optimistic "live" avoids confusing
    # operators with a flickering "ended/upcoming" label during the gap.
    return "live"


def _serialize_schedule(
    schedule: Schedule,
    active_session_ids: set[str] | None = None,
    now: datetime | None = None,
) -> ScheduleResponse:
    """Build a ScheduleResponse with runtime_status populated.

    For batch endpoints (list_schedules, get_my_schedules) pass a single
    pre-snapshotted `active_session_ids` and `now` so we don't re-fetch them
    per row. Single-row callers may omit both — the helper snapshots once.
    """
    if active_session_ids is None:
        active_session_ids = session_manager.list_active_session_ids()
    if now is None:
        now = datetime.now()
    response = ScheduleResponse.model_validate(schedule)
    response.runtime_status = _compute_runtime_status(schedule, active_session_ids, now)
    return response


@router.get("/", response_model=list[ScheduleResponse], status_code=status.HTTP_200_OK)
def list_schedules(
    day: int | None = Query(None, ge=0, le=6, description="Filter by day (0=Monday, 6=Sunday)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **List All Schedules**

    Get all active schedules, optionally filtered by day of week.

    - **day**: Optional day filter (0=Monday, 6=Sunday)

    Returns list of schedules with faculty and room information.

    Requires authentication.
    """
    schedule_repo = ScheduleRepository(db)

    if day is not None:
        schedules = schedule_repo.get_by_day(day)
    else:
        schedules = schedule_repo.get_all()

    # Snapshot once and reuse across rows so all rows are derived against
    # the same instant — a row processed half a second after another that
    # crossed end_time would otherwise flip from "live" → "ended" mid-list.
    active = session_manager.list_active_session_ids()
    now = datetime.now()
    return [_serialize_schedule(s, active, now) for s in schedules]


@router.get("/me", response_model=list[ScheduleResponse], status_code=status.HTTP_200_OK)
def get_my_schedules(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get My Schedules**

    Get schedules for the current user:
    - **Students**: Enrolled schedules
    - **Faculty**: Teaching schedules

    Returns list of relevant schedules with eager-loaded faculty and room info.

    Requires authentication.
    """
    from app.models.enrollment import Enrollment

    base_query = db.query(Schedule).options(
        joinedload(Schedule.faculty),
        joinedload(Schedule.room),
    )

    if current_user.role == UserRole.FACULTY:
        schedules = base_query.filter(
            Schedule.faculty_id == current_user.id,
            Schedule.is_active,
        ).all()
        logger.info(
            f"GET /schedules/me — faculty={current_user.email} "
            f"(id={current_user.id}), found {len(schedules)} schedule(s)"
        )
    elif current_user.role == UserRole.STUDENT:
        # Single query: join enrollments → schedules with faculty/room
        schedules = (
            base_query.join(Enrollment, Enrollment.schedule_id == Schedule.id)
            .filter(
                Enrollment.student_id == current_user.id,
                Schedule.is_active,
            )
            .all()
        )
        enrollment_count = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).count()
        logger.info(
            f"GET /schedules/me — student={current_user.email} "
            f"(id={current_user.id}), enrollments={enrollment_count}, "
            f"active schedules={len(schedules)}"
        )
    else:
        schedules = base_query.filter(Schedule.is_active).all()
        logger.info(f"GET /schedules/me — admin={current_user.email}, found {len(schedules)} schedule(s)")

    active = session_manager.list_active_session_ids()
    now = datetime.now()
    return [_serialize_schedule(s, active, now) for s in schedules]


@router.get("/{schedule_id}", response_model=ScheduleResponse, status_code=status.HTTP_200_OK)
def get_schedule(schedule_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get Schedule by ID**

    Retrieve detailed schedule information.

    - **schedule_id**: Schedule UUID

    Requires authentication.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    return _serialize_schedule(schedule)


@router.get("/{schedule_id}/students", response_model=ScheduleWithStudents, status_code=status.HTTP_200_OK)
def get_enrolled_students(
    schedule_id: str,
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Get Enrolled Students** (Faculty/Admin Only)

    Get list of students enrolled in a schedule.

    - **schedule_id**: Schedule UUID

    Returns schedule with enrolled students list.

    Requires faculty or admin authentication.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    students = schedule_repo.get_enrolled_students(schedule_id)

    # Single batch lookup so we don't N+1 face_registrations per row. The
    # set comprehension narrows to active registrations only — the model
    # has a unique constraint on user_id but `is_active` can flip false
    # when an admin resets a student's face from the user detail page.
    student_ids = [s.id for s in students]
    registered_ids: set[str] = set()
    if student_ids:
        rows = (
            db.query(FaceRegistration.user_id)
            .filter(
                FaceRegistration.user_id.in_(student_ids),
                FaceRegistration.is_active.is_(True),
            )
            .all()
        )
        registered_ids = {str(r[0]) for r in rows}

    # Convert to response format
    response = _serialize_schedule(schedule)
    student_info = [
        {
            "id": str(s.id),
            "student_id": s.student_id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "email": s.email,
            "has_face_registered": str(s.id) in registered_ids,
        }
        for s in students
    ]

    return ScheduleWithStudents(**response.model_dump(), enrolled_students=student_info)


@router.get(
    "/{schedule_id}/sessions",
    response_model=list[SessionSummary],
    status_code=status.HTTP_200_OK,
)
def get_schedule_sessions(
    schedule_id: str,
    start_date: date | None = Query(None, description="Earliest session date (inclusive)"),
    end_date: date | None = Query(None, description="Latest session date (inclusive)"),
    limit: int = Query(50, ge=1, le=500, description="Max sessions to return"),
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """**Get Session History** (Faculty/Admin Only)

    List past sessions for a schedule with per-status counts and the
    derived attendance rate. A "session" is the set of attendance_records
    sharing the same `date` for this schedule_id. Ordered newest first
    and capped by `limit` (default 50).

    Each row carries the schedule's canonical start/end window — the
    actual session boundaries are inferable from presence_logs but at
    this granularity the schedule window is what operators expect.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    import uuid as _uuid

    schedule_uuid = _uuid.UUID(schedule_id) if isinstance(schedule_id, str) else schedule_id

    # Single GROUP BY date,status pass — one row per (date, status) pair.
    # We pivot client-side because the conditional COUNT pattern below
    # works on both Postgres and SQLite without engine-specific filter
    # syntax.
    q = (
        db.query(
            AttendanceRecord.date.label("date"),
            AttendanceRecord.status.label("status"),
            func.count(AttendanceRecord.id).label("n"),
        )
        .filter(AttendanceRecord.schedule_id == schedule_uuid)
        .group_by(AttendanceRecord.date, AttendanceRecord.status)
    )
    if start_date is not None:
        q = q.filter(AttendanceRecord.date >= start_date)
    if end_date is not None:
        q = q.filter(AttendanceRecord.date <= end_date)

    grouped: dict[date, dict[str, int]] = {}
    for row in q.all():
        d = row.date
        # SQLAlchemy returns the enum's value (a string) on Postgres; on
        # SQLite it's the enum object. Normalize to the string value.
        status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
        bucket = grouped.setdefault(d, {})
        bucket[status_val] = bucket.get(status_val, 0) + int(row.n)

    sessions: list[SessionSummary] = []
    for d in sorted(grouped.keys(), reverse=True)[:limit]:
        b = grouped[d]
        present = b.get(AttendanceStatus.PRESENT.value, 0)
        late = b.get(AttendanceStatus.LATE.value, 0)
        absent = b.get(AttendanceStatus.ABSENT.value, 0)
        early_leave = b.get(AttendanceStatus.EARLY_LEAVE.value, 0)
        excused = b.get(AttendanceStatus.EXCUSED.value, 0)
        total = present + late + absent + early_leave + excused
        rate = round(((present + late) / total) * 100, 1) if total > 0 else None
        sessions.append(
            SessionSummary(
                date=d,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                present=present,
                late=late,
                absent=absent,
                early_leave=early_leave,
                excused=excused,
                attendance_rate=rate,
                total_records=total,
            )
        )

    return sessions


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule_data: ScheduleCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Create Schedule** (Admin Only)

    Create a new class schedule.

    - **schedule_data**: Schedule information

    Requires admin authentication.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.create(schedule_data.model_dump())

    logger.info(f"Schedule created: {schedule.subject_code} by admin {current_user.email}")

    # Audit + System Activity feed. Wrapped in a try so a logging failure
    # never undoes the schedule create.
    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="create",
            target_type="schedule",
            target_id=str(schedule.id),
            details=f"Schedule created: {schedule.subject_code} ({schedule.subject_name})",
            activity_summary=(
                f"Schedule created: {schedule.subject_code} — {schedule.subject_name}"
            ),
            activity_payload={
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "day_of_week": schedule.day_of_week,
                "start_time": str(schedule.start_time) if schedule.start_time else None,
                "end_time": str(schedule.end_time) if schedule.end_time else None,
                "room_id": str(schedule.room_id) if schedule.room_id else None,
                "faculty_id": str(schedule.faculty_id) if schedule.faculty_id else None,
            },
            activity_severity="success",
        )
    except Exception:
        logger.warning("log_audit failed for schedule.create", exc_info=True)

    return _serialize_schedule(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse, status_code=status.HTTP_200_OK)
def update_schedule(
    schedule_id: str,
    update_data: ScheduleUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Update Schedule** (Admin Only)

    Update schedule information.

    - **schedule_id**: Schedule UUID
    - **update_data**: Fields to update (all optional)

    Requires admin authentication.
    """
    schedule_repo = ScheduleRepository(db)

    # Filter out None values
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

    schedule = schedule_repo.update(schedule_id, update_dict)

    logger.info(f"Schedule updated: {schedule_id} by admin {current_user.email}")

    try:
        from app.utils.audit import log_audit

        # Stringify payload values so JSONB serialization never trips on
        # time / UUID objects from the update_dict pass-through.
        safe_changes = {k: str(v) if v is not None else None for k, v in update_dict.items()}

        log_audit(
            db,
            admin_id=current_user.id,
            action="update",
            target_type="schedule",
            target_id=str(schedule.id),
            details=f"Schedule updated: {schedule.subject_code}",
            activity_summary=(
                f"Schedule updated: {schedule.subject_code} — {schedule.subject_name}"
            ),
            activity_payload={
                "subject_code": schedule.subject_code,
                "changes": safe_changes,
            },
        )
    except Exception:
        logger.warning("log_audit failed for schedule.update", exc_info=True)

    return _serialize_schedule(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_200_OK)
def delete_schedule(
    schedule_id: str, current_user: User = Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)
):
    """
    **Delete Schedule** (Admin Only)

    Deactivate a schedule (soft delete).

    - **schedule_id**: Schedule UUID

    Requires admin authentication.
    """
    schedule_repo = ScheduleRepository(db)
    # Capture identifying fields *before* the delete so the audit summary
    # has a human-readable name even on hard-delete (soft-delete keeps the
    # row but a future migration may flip this).
    target = schedule_repo.get_by_id(schedule_id)
    target_subject_code = target.subject_code if target else None
    target_subject_name = target.subject_name if target else None

    schedule_repo.delete(schedule_id)

    logger.info(f"Schedule deleted: {schedule_id} by admin {current_user.email}")

    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="delete",
            target_type="schedule",
            target_id=str(schedule_id),
            details=(
                f"Schedule deleted: {target_subject_code or schedule_id}"
            ),
            activity_summary=(
                f"Schedule deleted: {target_subject_code or schedule_id}"
                + (f" — {target_subject_name}" if target_subject_name else "")
            ),
            activity_payload={
                "subject_code": target_subject_code,
                "subject_name": target_subject_name,
            },
            activity_severity="warn",
        )
    except Exception:
        logger.warning("log_audit failed for schedule.delete", exc_info=True)

    return {"success": True, "message": "Schedule deleted successfully"}


@router.patch("/{schedule_id}/config", response_model=ScheduleResponse, status_code=status.HTTP_200_OK)
def update_schedule_config(
    schedule_id: str,
    config_data: ScheduleConfigUpdate,
    http_request: Request,
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Update Schedule Config** (Faculty/Admin)

    Faculty can update attendance settings for their own schedules.
    Takes effect immediately on running sessions.

    - **schedule_id**: Schedule UUID
    - **early_leave_timeout_minutes**: 1-15 minutes
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    # Faculty can only update their own schedules
    if current_user.role == UserRole.FACULTY and str(schedule.faculty_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify another faculty's schedule")

    # Persist to DB
    updated = schedule_repo.update(schedule_id, config_data.model_dump())

    # Update running pipeline if session is active (mid-session change)
    pipelines = getattr(http_request.app.state, "session_pipelines", {})
    pipeline = pipelines.get(schedule_id)
    if pipeline and pipeline.is_running:
        timeout_seconds = config_data.early_leave_timeout_minutes * 60.0
        pipeline.update_early_leave_timeout(timeout_seconds)

    logger.info(
        f"Schedule config updated: {schedule_id} "
        f"early_leave_timeout={config_data.early_leave_timeout_minutes}min "
        f"by {current_user.email}"
    )

    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="update",
            target_type="schedule",
            target_id=str(schedule_id),
            details=(
                f"Config updated: early_leave_timeout="
                f"{config_data.early_leave_timeout_minutes}min"
            ),
            activity_summary=(
                f"Schedule config updated: {schedule.subject_code} — "
                f"early-leave timeout {config_data.early_leave_timeout_minutes}min"
            ),
            activity_payload={
                "subject_code": schedule.subject_code,
                "early_leave_timeout_minutes": config_data.early_leave_timeout_minutes,
                "actor_role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            },
        )
    except Exception:
        logger.warning("log_audit failed for schedule.config_update", exc_info=True)

    return _serialize_schedule(updated)


# ===================================================================
# Manual Enrollment
# ===================================================================


@router.post("/{schedule_id}/enroll/{student_user_id}", status_code=status.HTTP_201_CREATED)
def enroll_student(
    schedule_id: str,
    student_user_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Enroll Student** (Admin Only)

    Manually enroll a student in a schedule.
    """
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    student = db.query(User).filter(User.id == student_user_id, User.role == UserRole.STUDENT).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    existing = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_user_id, Enrollment.schedule_id == schedule_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Student is already enrolled in this schedule")

    enrollment = Enrollment(student_id=student_user_id, schedule_id=schedule_id)
    db.add(enrollment)
    db.commit()

    logger.info(f"Manual enrollment: {student.email} -> {schedule.subject_code} by {current_user.email}")

    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="create",
            target_type="enrollment",
            target_id=str(enrollment.id),
            details=(
                f"Enrolled {student.email} -> {schedule.subject_code}"
            ),
            activity_summary=(
                f"Enrolled {student.first_name} {student.last_name} "
                f"in {schedule.subject_code}"
            ),
            activity_payload={
                "student_user_id": str(student_user_id),
                "schedule_id": str(schedule_id),
                "subject_code": schedule.subject_code,
                "student_email": student.email,
            },
        )
    except Exception:
        logger.warning("log_audit failed for enrollment.create", exc_info=True)

    return {"success": True, "message": f"{student.first_name} {student.last_name} enrolled successfully"}


@router.delete("/{schedule_id}/enroll/{student_user_id}", status_code=status.HTTP_200_OK)
def unenroll_student(
    schedule_id: str,
    student_user_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Unenroll Student** (Admin Only)

    Remove a student's enrollment from a schedule.
    """
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_user_id, Enrollment.schedule_id == schedule_id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    enrollment_id = str(enrollment.id)
    # Resolve names *before* delete so the audit row carries human context
    # even though the FK rows are gone.
    student = db.query(User).filter(User.id == student_user_id).first()
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()

    db.delete(enrollment)
    db.commit()

    logger.info(f"Manual unenrollment: user {student_user_id} from schedule {schedule_id} by {current_user.email}")

    try:
        from app.utils.audit import log_audit

        student_label = (
            f"{student.first_name} {student.last_name}".strip()
            if student
            else str(student_user_id)
        )
        subject_code = schedule.subject_code if schedule else str(schedule_id)
        log_audit(
            db,
            admin_id=current_user.id,
            action="delete",
            target_type="enrollment",
            target_id=enrollment_id,
            details=(
                f"Unenrolled user {student_user_id} from schedule {schedule_id}"
            ),
            activity_summary=f"Unenrolled {student_label} from {subject_code}",
            activity_payload={
                "student_user_id": str(student_user_id),
                "schedule_id": str(schedule_id),
                "subject_code": subject_code,
                "student_email": student.email if student else None,
            },
            activity_severity="warn",
        )
    except Exception:
        logger.warning("log_audit failed for enrollment.delete", exc_info=True)

    return {"success": True, "message": "Student unenrolled successfully"}


@router.get("/student/{student_user_id}/enrollments", status_code=status.HTTP_200_OK)
def get_student_enrollments(
    student_user_id: str,
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    """
    **Get Student Enrollments** (Admin/Faculty)

    Get schedules a student is enrolled in, paginated.

    - **limit**: max results per page (default 20, max 100)
    - **offset**: number of results to skip (default 0)

    Returns `{ items, total, limit, offset, has_more }`.
    """
    base_query = db.query(Enrollment).filter(Enrollment.student_id == student_user_id)
    total = base_query.count()

    enrollments = (
        base_query
        .options(joinedload(Enrollment.schedule).joinedload(Schedule.faculty))
        .options(joinedload(Enrollment.schedule).joinedload(Schedule.room))
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    active = session_manager.list_active_session_ids()
    now = datetime.now()
    items = [
        {
            "enrollment_id": str(e.id),
            "schedule_id": str(e.schedule_id),
            "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
            "schedule": _serialize_schedule(e.schedule, active, now).model_dump() if e.schedule else None,
        }
        for e in enrollments
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@router.get("/student/{student_user_id}/enrollments/ids", status_code=status.HTTP_200_OK)
def get_student_enrollment_ids(
    student_user_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    """
    **Get Student Enrollment Schedule IDs** (Admin/Faculty)

    Returns a flat list of schedule_ids the student is enrolled in.
    Used by the admin portal's Enroll-in-Schedule dialog to hide already-
    enrolled schedules without loading the paginated enrollment payload.
    """
    rows = (
        db.query(Enrollment.schedule_id)
        .filter(Enrollment.student_id == student_user_id)
        .all()
    )
    return {"schedule_ids": [str(r[0]) for r in rows]}
