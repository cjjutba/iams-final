"""
Authentication Router

API endpoints for authentication: register, login, token refresh,
password management, and student ID verification.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.rate_limiter import limiter
from app.schemas.auth import (
    CheckStudentIDRequest,
    CheckStudentIDResponse,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    VerifyStudentIDRequest,
    VerifyStudentIDResponse,
)
from app.schemas.user import PasswordChange, UserResponse
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user

router = APIRouter()


# ===================================================================
# FUN-01-01a: Check Student ID Availability
# ===================================================================


@router.post(
    "/check-student-id",
    response_model=CheckStudentIDResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def check_student_id(
    request: Request,
    body: CheckStudentIDRequest,
    db: Session = Depends(get_db),
):
    """
    **Step 1a of Student Registration: Check Student ID**

    Checks if a student ID exists in university records and is available
    for registration. Does not require birthdate.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    result = auth_service.check_student_id(body.student_id)
    return CheckStudentIDResponse(**result)


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

    Validates the student ID and birthdate against university records.
    Two-factor verification prevents unauthorized access to student information.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    result = auth_service.verify_student_id(body.student_id, body.birthdate)
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
# FUN-01-03: Login
# ===================================================================


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    **Login**

    Authenticate user and receive access tokens.
    Rate limited to 10 requests/minute.
    """
    import logging as _logging

    from app.services import security_tracker
    from app.services.notification_service import notify_admins
    from app.utils.exceptions import AuthenticationError

    _logger = _logging.getLogger(__name__)

    auth_service = AuthService(db)
    try:
        user, tokens = auth_service.login(body.identifier, body.password)
    except AuthenticationError:
        # Phase-4: track failed-login bursts and notify admins on the
        # exact attempt that crosses the threshold (3 in 5 min). The
        # tracker is idempotent on missing Redis — degrades to no-op.
        try:
            count, just_crossed = await security_tracker.record_failed_login(
                body.identifier
            )
            if just_crossed:
                try:
                    await notify_admins(
                        db,
                        title="Failed login burst detected",
                        message=(
                            "3+ failed login attempts in 5 minutes for one "
                            "identifier. Possible credential probing."
                        ),
                        notification_type="failed_login_burst",
                        severity="warn",
                        preference_key="security_alerts",
                        send_email=True,
                        dedup_window_seconds=900,
                        reference_id=(
                            f"login_burst:"
                            f"{security_tracker.hash_identifier(body.identifier)}"
                        ),
                        reference_type="composite_key",
                        toast_type="warning",
                    )
                except Exception:
                    _logger.exception("Failed to notify admins of login burst")
        except Exception:
            _logger.exception("Failed to record failed login attempt")
        # Re-raise so the global IAMS handler turns this into a 401.
        raise

    # Phase-4: successful login resets the burst counter for this identifier.
    try:
        await security_tracker.clear_failed_login(body.identifier)
    except Exception:
        _logger.exception("Failed to clear failed-login counter")

    # Record the login in both audit_logs (legacy) and activity_events
    # (System Activity page). The log_audit helper derives the event type
    # from (action, target_type) — here "login" + role gives us
    # ADMIN_LOGIN / FACULTY_LOGIN / STUDENT_LOGIN automatically.
    try:
        from app.utils.audit import log_audit

        role = (
            user.role.value if hasattr(user.role, "value") else str(user.role)
        ).lower()
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        log_audit(
            db,
            admin_id=user.id,
            action="login",
            target_type=role,
            target_id=str(user.id),
            details=f"Identifier: {body.identifier}",
            activity_summary=f"{full_name or user.email} logged in as {role.upper()}",
            activity_payload={
                "user_id": str(user.id),
                "role": role,
                "email": user.email,
            },
        )
    except Exception:
        # Audit is best-effort — never block login on it.
        pass

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_type=tokens["token_type"],
        user=UserResponse.model_validate(user),
    )


# ===================================================================
# FUN-01-04: Refresh Token
# ===================================================================


@router.post("/refresh", status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    **Refresh Access Token**

    Generate a new access token using a refresh token.
    Rate limited to 10 requests/minute.
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
    """
    return UserResponse.model_validate(current_user)


# ===================================================================
# FUN-01-06: Request Password Reset
# ===================================================================


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request_obj: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    **Forgot Password**

    Request a password reset link.
    Always returns success to prevent email enumeration attacks.
    Rate limited to 10 requests/minute.
    """
    import logging as _logging

    _logger = _logging.getLogger(__name__)

    auth_service = AuthService(db)
    result = auth_service.forgot_password(body.email)

    # Phase-4: drop an in-app notification on the affected user's bell.
    # send_email=False because the actual reset *link* is sent by the
    # auth_service flow with its own email; this is the in-app
    # bell/toast confirmation. Only emitted when the email maps to a
    # real account — silently no-op for unknown emails so the route's
    # enumeration-safe response shape is preserved.
    try:
        target_user = (
            db.query(User).filter(User.email == body.email).first()
            if body.email
            else None
        )
        if target_user is not None:
            from app.services.notification_service import notify

            await notify(
                db,
                user_id=str(target_user.id),
                title="Password reset requested",
                message=(
                    "A password reset was requested for your account. "
                    "Check your email for the reset link."
                ),
                notification_type="password_reset_requested",
                severity="info",
                preference_key=None,
                send_email=False,
                dedup_window_seconds=300,
                reference_id=str(target_user.id),
                reference_type="user",
                toast_type="info",
            )
    except Exception:
        _logger.exception("Failed to notify user of password reset request")

    return result


# ===================================================================
# Password & Profile Management
# ===================================================================


@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def change_password(
    request: Request,
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Change Password**

    Change the current user's password.
    Rate limited to 10 requests/minute.
    """
    import logging as _logging

    _logger = _logging.getLogger(__name__)

    auth_service = AuthService(db)
    auth_service.change_password(
        str(current_user.id),
        body.old_password,
        body.new_password,
    )

    # Phase-4: notify the user that their password changed. Critical for
    # detecting account compromise — if it wasn't them, they need to act.
    try:
        from app.services.notification_service import notify

        await notify(
            db,
            user_id=str(current_user.id),
            title="Password changed",
            message=(
                "Your password was changed. If this wasn't you, contact "
                "an administrator immediately."
            ),
            notification_type="password_changed",
            severity="info",
            preference_key="security_alerts",
            send_email=True,
            email_template="password_changed",
            email_context={
                "user_name": current_user.full_name or current_user.email,
            },
            dedup_window_seconds=0,
            reference_id=str(current_user.id),
            reference_type="user",
            toast_type="info",
        )
    except Exception:
        _logger.exception("Failed to notify user of password change")

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
