"""
Schedules Router

API endpoints for class schedule management.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload

from app.config import logger
from app.database import get_db
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate, ScheduleWithStudents
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
        from fastapi import HTTPException

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
        from fastapi import HTTPException

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
