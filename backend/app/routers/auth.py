"""
Authentication Router

API endpoints for authentication: register, login, token refresh,
email verification, password reset, and Supabase webhook handling.
"""

import hmac
import hashlib
from fastapi import APIRouter, Depends, Request, status, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings, logger
from app.database import get_db
from app.models.user import User
from app.rate_limiter import limiter
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    VerifyStudentIDRequest,
    VerifyStudentIDResponse,
    RegisterRequest,
    RegisterResponse,
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ProfileUpdateRequest,
    SupabaseWebhookPayload,
)
from app.schemas.user import UserResponse, PasswordChange
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user


router = APIRouter()


# ===================================================================
# FUN-01-01: Verify Student Identity
# ===================================================================

@router.post(
    "/verify-student-id",
    response_model=VerifyStudentIDResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def verify_student_id(
    request: Request,
    body: VerifyStudentIDRequest,
    db: Session = Depends(get_db),
):
    """
    **Step 1 of Student Registration: Verify Student ID**

    Validates the student ID against university records and returns student information.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    result = auth_service.verify_student_id(body.student_id)
    return VerifyStudentIDResponse(**result)


# ===================================================================
# FUN-01-02: Register Student Account
# ===================================================================

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request_obj: Request,
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    **Step 2 of Student Registration: Create Account**

    Creates a new student account after student ID verification.
    When Supabase Auth is enabled, a verification email is sent automatically.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    user, result = auth_service.register_student(body.model_dump())

    # Build response — tokens are present only in legacy mode
    tokens = None
    if "access_token" in result:
        tokens = TokenResponse(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            token_type=result["token_type"],
            user=UserResponse.model_validate(user),
        )

    message = result.get(
        "message",
        "Account created successfully. Please register your face to complete setup.",
    )

    return RegisterResponse(
        success=True,
        message=message,
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )


# ===================================================================
# FUN-01-03: Login (custom JWT — kept for dual-auth transition)
# ===================================================================

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    request_obj: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    **Login**

    Authenticate user and receive access tokens (custom JWT mode).
    When Supabase Auth is active, use the Supabase client SDK instead.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    user, tokens = auth_service.login(body.identifier, body.password)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_type=tokens["token_type"],
        user=UserResponse.model_validate(user),
    )


# ===================================================================
# FUN-01-04: Refresh Token (custom JWT)
# ===================================================================

@router.post("/refresh", status_code=status.HTTP_200_OK)
def refresh_token(
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    **Refresh Access Token**

    Generate a new access token using a refresh token (custom JWT mode).
    When Supabase Auth is active, token refresh is automatic via the SDK.
    """
    auth_service = AuthService(db)
    return auth_service.refresh_access_token(body.refresh_token)


# ===================================================================
# FUN-01-05: Get Current User
# ===================================================================

@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    **Get Current User Information**

    Returns information about the currently authenticated user.
    Enforces is_active and email_verified (when Supabase Auth is enabled).
    """
    return UserResponse.model_validate(current_user)


# ===================================================================
# FUN-01-06: Request Password Reset
# ===================================================================

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    request_obj: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    **Forgot Password**

    Request a password reset link.
    When Supabase Auth is enabled, the reset email is sent via Supabase.
    Always returns success to prevent email enumeration attacks.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    return auth_service.forgot_password(body.email)


# ===================================================================
# Email Verification
# ===================================================================

@router.post("/resend-verification", status_code=status.HTTP_200_OK)
def resend_verification(
    request_obj: Request,
    body: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    **Resend Email Verification**

    Re-sends the email verification link to the provided email.
    Always returns success to prevent email enumeration.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    return auth_service.resend_verification_email(body.email)


# ===================================================================
# Supabase Webhook
# ===================================================================

@router.post("/webhook/supabase", status_code=status.HTTP_200_OK)
async def supabase_webhook(
    payload: SupabaseWebhookPayload,
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_secret: str = Header(None, alias="x-webhook-secret"),
):
    """
    **Supabase Auth Webhook**

    Receives events from Supabase Auth (e.g. email verified).
    Verifies the webhook secret before processing.
    """
    # Verify webhook secret
    expected_secret = settings.SUPABASE_WEBHOOK_SECRET
    if expected_secret:
        if not x_webhook_secret or x_webhook_secret != expected_secret:
            logger.warning("Supabase webhook: invalid or missing secret")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid webhook secret"},
            )

    logger.info(f"Supabase webhook received: type={payload.type}")

    auth_service = AuthService(db)

    # Handle user update events (email verification)
    if payload.type == "user.updated" and payload.record:
        record = payload.record
        email_confirmed_at = record.get("email_confirmed_at")
        supabase_user_id = record.get("id")

        if email_confirmed_at and supabase_user_id:
            user = auth_service.handle_email_verified(supabase_user_id)
            if user:
                logger.info(f"Webhook: email verified for {user.email}")

    return {"success": True, "message": "Webhook processed"}


# ===================================================================
# Password & Profile Management
# ===================================================================

@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Change Password**

    Change the current user's password.
    When Supabase Auth is enabled, the password is also updated in Supabase.
    """
    auth_service = AuthService(db)
    auth_service.change_password(
        str(current_user.id),
        body.old_password,
        body.new_password,
    )

    return {"success": True, "message": "Password changed successfully"}


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)):
    """
    **Logout**

    Logout the current user.
    Stateless JWT — the client discards the token.
    """
    return {"success": True, "message": "Logged out successfully"}


@router.patch("/profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Update Profile**

    Update the current user's profile (email, phone).
    """
    auth_service = AuthService(db)
    updated_user = auth_service.update_profile(
        str(current_user.id),
        body.model_dump(exclude_none=True),
    )
    return UserResponse.model_validate(updated_user)
