"""
Schedules Router

API endpoints for class schedule management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.config import logger
from app.database import get_db
from app.models.enrollment import Enrollment
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import (
    ScheduleConfigUpdate,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    ScheduleWithStudents,
)
from app.utils.dependencies import get_current_user, require_role

router = APIRouter()


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

    return [ScheduleResponse.model_validate(s) for s in schedules]


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

    return [ScheduleResponse.model_validate(s) for s in schedules]


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

    return ScheduleResponse.model_validate(schedule)


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

    # Convert to response format
    response = ScheduleResponse.model_validate(schedule)
    student_info = [
        {
            "id": str(s.id),
            "student_id": s.student_id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "email": s.email,
        }
        for s in students
    ]

    return ScheduleWithStudents(**response.model_dump(), enrolled_students=student_info)


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

    return ScheduleResponse.model_validate(schedule)


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

    return ScheduleResponse.model_validate(schedule)


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
    schedule_repo.delete(schedule_id)

    logger.info(f"Schedule deleted: {schedule_id} by admin {current_user.email}")

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

    return ScheduleResponse.model_validate(updated)


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

    db.delete(enrollment)
    db.commit()

    logger.info(f"Manual unenrollment: user {student_user_id} from schedule {schedule_id} by {current_user.email}")
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

    items = [
        {
            "enrollment_id": str(e.id),
            "schedule_id": str(e.schedule_id),
            "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
            "schedule": ScheduleResponse.model_validate(e.schedule).model_dump() if e.schedule else None,
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
