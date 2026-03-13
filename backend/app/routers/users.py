"""
Users Router

API endpoints for user management operations.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService
from app.utils.dependencies import get_current_admin, get_current_user

router = APIRouter()


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

    return [UserResponse.from_orm(user) for user in users]


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
    return UserResponse.from_orm(user)


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
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

    user = user_service.update_user(user_id, update_dict)
    return UserResponse.from_orm(user)


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

    return {"success": True, "message": "User reactivated successfully", "user": UserResponse.from_orm(user)}
