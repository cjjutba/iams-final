"""
Users Router

API endpoints for user management operations.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminCreateUser,
    CreateStudentRecord,
    StudentRecordResponse,
    StudentRecordWithStatusResponse,
    UpdateStudentRecord,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService
from app.utils.dependencies import get_current_admin, get_current_user

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    body: AdminCreateUser,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Create User** (Admin Only)

    Create a new user account (faculty or admin).
    """
    user_service = UserService(db)
    user = user_service.admin_create_user(body)
    return UserResponse.model_validate(user)


@router.post("/student-records", response_model=StudentRecordResponse, status_code=status.HTTP_201_CREATED)
def create_student_record(
    body: CreateStudentRecord,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Create Student Record** (Admin Only)

    Add a student to the student_records registry.
    The student can then self-register via the mobile app.
    """
    user_service = UserService(db)
    record = user_service.create_student_record(body)
    return StudentRecordResponse.model_validate(record)


@router.get(
    "/student-records",
    response_model=list[StudentRecordWithStatusResponse],
    status_code=status.HTTP_200_OK,
)
def list_student_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **List Student Records** (Admin Only)

    Get all student records with app registration status.
    """
    user_service = UserService(db)
    results = user_service.get_student_records_with_status(skip, limit)
    return [
        StudentRecordWithStatusResponse.model_validate({
            **StudentRecordResponse.model_validate(r["record"]).model_dump(),
            "user_id": r["user_id"],
            "is_registered": r["is_registered"],
            "has_face_registered": r["has_face_registered"],
        })
        for r in results
    ]


@router.get(
    "/student-records/{student_id}",
    response_model=StudentRecordWithStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_student_record(
    student_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Get Student Record** (Admin Only)

    Retrieve a single student record with registration status.
    """
    user_service = UserService(db)
    r = user_service.get_student_record(student_id)
    return StudentRecordWithStatusResponse.model_validate({
        **StudentRecordResponse.model_validate(r["record"]).model_dump(),
        "user_id": r["user_id"],
        "is_registered": r["is_registered"],
        "has_face_registered": r["has_face_registered"],
    })


@router.patch(
    "/student-records/{student_id}",
    response_model=StudentRecordResponse,
    status_code=status.HTTP_200_OK,
)
def update_student_record(
    student_id: str,
    body: UpdateStudentRecord,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Update Student Record** (Admin Only)

    Update a student record in the registry.
    """
    user_service = UserService(db)
    update_dict = {k: v for k, v in body.model_dump().items() if v is not None}
    record = user_service.update_student_record(student_id, update_dict)
    return StudentRecordResponse.model_validate(record)


@router.delete("/student-records/{student_id}", status_code=status.HTTP_200_OK)
def deactivate_student_record(
    student_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Deactivate Student Record** (Admin Only)

    Soft-delete a student record from the registry.
    """
    user_service = UserService(db)
    user_service.deactivate_student_record(student_id)
    return {"success": True, "message": "Student record deactivated"}


@router.get("/", response_model=list[UserResponse], status_code=status.HTTP_200_OK)
def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    role: UserRole = Query(None, description="Filter by user role"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **List All Users** (Admin Only)

    Get a paginated list of users, optionally filtered by role.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **role**: Optional role filter (student, faculty, admin)

    Requires admin authentication.
    """
    user_service = UserService(db)

    if role:
        users = user_service.get_users_by_role(role, skip, limit)
    else:
        users = user_service.get_all_users(skip, limit)

    return [UserResponse.model_validate(user) for user in users]


@router.get("/statistics", status_code=status.HTTP_200_OK)
def get_user_statistics(current_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    **Get User Statistics** (Admin Only)

    Get user count statistics by role.

    Returns total users, students, faculty, and admins count.

    Requires admin authentication.
    """
    user_service = UserService(db)
    stats = user_service.get_statistics()

    return {"success": True, "data": stats}


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_user(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get User by ID**

    Retrieve user information by user ID.

    - **user_id**: User UUID

    Students can only view their own profile.
    Faculty and admins can view any user.

    Requires authentication.
    """
    user_service = UserService(db)

    # Students can only view their own profile
    if current_user.role == UserRole.STUDENT and str(current_user.id) != user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only view their own profile")

    user = user_service.get_user(user_id)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_user(
    user_id: str, update_data: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    **Update User**

    Update user information.

    - **user_id**: User UUID
    - **update_data**: Fields to update (all optional)

    Students can only update their own profile.
    Faculty and admins can update any user.

    Requires authentication.
    """
    user_service = UserService(db)

    # Students can only update their own profile
    if current_user.role == UserRole.STUDENT and str(current_user.id) != user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only update their own profile")

    # Filter out None values
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

    user = user_service.update_user(user_id, update_dict)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def deactivate_user(user_id: str, current_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    **Deactivate User** (Admin Only)

    Deactivate a user account (soft delete).

    - **user_id**: User UUID

    Deactivated users cannot login but their data is preserved.

    Requires admin authentication.
    """
    user_service = UserService(db)
    user_service.deactivate_user(user_id)

    return {"success": True, "message": "User deactivated successfully"}


@router.post("/{user_id}/reactivate", status_code=status.HTTP_200_OK)
def reactivate_user(user_id: str, current_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    **Reactivate User** (Admin Only)

    Reactivate a previously deactivated user account.

    - **user_id**: User UUID

    Requires admin authentication.
    """
    user_service = UserService(db)
    user = user_service.reactivate_user(user_id)

    return {"success": True, "message": "User reactivated successfully", "user": UserResponse.model_validate(user)}
