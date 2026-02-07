"""
Authentication Router

API endpoints for authentication: register, login, token refresh, etc.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    VerifyStudentIDRequest,
    VerifyStudentIDResponse,
    RegisterRequest,
    RegisterResponse,
    ForgotPasswordRequest,
    ProfileUpdateRequest
)
from app.schemas.user import UserResponse, PasswordChange
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user


router = APIRouter()


@router.post("/verify-student-id", response_model=VerifyStudentIDResponse, status_code=status.HTTP_200_OK)
def verify_student_id(
    request: VerifyStudentIDRequest,
    db: Session = Depends(get_db)
):
    """
    **Step 1 of Student Registration: Verify Student ID**

    Validates the student ID against university records and returns student information.

    - **student_id**: Student ID to verify

    Returns student information if valid.
    """
    auth_service = AuthService(db)
    result = auth_service.verify_student_id(request.student_id)

    return VerifyStudentIDResponse(**result)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    **Step 2 of Student Registration: Create Account**

    Creates a new student account after student ID verification.

    - **student_id**: Verified student ID
    - **email**: Student email address
    - **password**: Account password (min 8 characters)
    - **first_name**: Student's first name
    - **last_name**: Student's last name
    - **phone**: Optional phone number

    Returns the created user and authentication tokens.

    **Note:** Face registration (Step 3) is done via `/face/register` endpoint.
    """
    auth_service = AuthService(db)
    user, tokens = auth_service.register_student(request.model_dump())

    return RegisterResponse(
        success=True,
        message="Account created successfully. Please register your face to complete setup.",
        user=UserResponse.from_orm(user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_type=tokens["token_type"],
            user=UserResponse.from_orm(user)
        )
    )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    **Login**

    Authenticate user and receive access tokens.

    - **identifier**: Email address or Student ID
    - **password**: Account password

    Returns access token, refresh token, and user information.
    """
    auth_service = AuthService(db)
    user, tokens = auth_service.login(request.identifier, request.password)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_type=tokens["token_type"],
        user=UserResponse.from_orm(user)
    )


@router.post("/refresh", status_code=status.HTTP_200_OK)
def refresh_token(
    request: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    **Refresh Access Token**

    Generate a new access token using a refresh token.

    - **refresh_token**: Valid refresh token

    Returns new access token.
    """
    auth_service = AuthService(db)
    result = auth_service.refresh_access_token(request.refresh_token)

    return result


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    **Get Current User Information**

    Returns information about the currently authenticated user.

    Requires authentication (Bearer token in Authorization header).
    """
    return UserResponse.from_orm(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    request: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Change Password**

    Change the current user's password.

    - **old_password**: Current password
    - **new_password**: New password (min 8 characters)

    Requires authentication.
    """
    auth_service = AuthService(db)
    auth_service.change_password(
        str(current_user.id),
        request.old_password,
        request.new_password
    )

    return {
        "success": True,
        "message": "Password changed successfully"
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)):
    """
    **Logout**

    Logout the current user.

    Note: Since we're using stateless JWT tokens, logout is handled client-side
    by discarding the tokens. This endpoint exists for consistency and future
    token blacklist implementation.

    Requires authentication.
    """
    return {
        "success": True,
        "message": "Logged out successfully"
    }


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    **Forgot Password**

    Request a password reset link. An email will be sent if the account exists.

    - **email**: Email address associated with the account

    Note: Always returns success to prevent email enumeration attacks.
    """
    auth_service = AuthService(db)
    result = auth_service.forgot_password(request.email)

    return result


@router.patch("/profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Update Profile**

    Update the current user's profile information.

    - **email**: New email address (optional)
    - **phone**: New phone number (optional)

    Only the fields provided will be updated.

    Requires authentication.
    """
    auth_service = AuthService(db)
    updated_user = auth_service.update_profile(
        str(current_user.id),
        request.model_dump(exclude_none=True)
    )

    return UserResponse.model_validate(updated_user)
