"""
Authentication Router

API endpoints for authentication: register, login, token refresh,
email verification, password reset, and Supabase webhook handling.
"""

import hmac
import hashlib
from fastapi import APIRouter, Depends, Request, status, Header
from fastapi.responses import JSONResponse, HTMLResponse
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
# Resolve Student ID to Email (for Supabase login)
# ===================================================================

@router.post("/resolve-email", status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def resolve_student_email(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    **Resolve a student ID to their registered email.**

    Used by the mobile app in Supabase Auth mode when a student logs in
    with their student ID instead of email. Accepts the same LoginRequest
    (identifier + password) but only uses the identifier field.

    The actual password verification happens via Supabase SDK on the client.
    This endpoint only resolves the student ID to an email.
    Rate limited to 10 requests/minute.
    """
    auth_service = AuthService(db)
    normalized = body.identifier.strip().upper()
    user = auth_service.user_repo.get_by_student_id(normalized)

    if not user:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "No account found for this student ID"},
        )

    return {"email": user.email}


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


@router.post("/check-email-verified", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
def check_email_verified(
    request: Request,
    body: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    **Check Email Verification Status**

    Public endpoint (no auth required) that checks whether a user's
    email has been verified. Checks Supabase Auth directly and syncs
    the result to the local database.

    Used by the mobile app's EmailVerificationScreen to poll for
    verification status after registration.
    """
    auth_service = AuthService(db)
    return auth_service.check_email_verified(body.email)


@router.get("/email-confirmed", response_class=HTMLResponse)
def email_confirmed_page():
    """
    **Auth Callback Landing Page**

    Only available when USE_SUPABASE_AUTH is enabled.

    Supabase redirects here after email confirmation AND password recovery.
    JavaScript detects `#type=recovery` in the URL hash to show either:
    - Email Verified confirmation (default / type=signup)
    - Password Reset form (type=recovery)
    """
    if not settings.USE_SUPABASE_AUTH:
        return HTMLResponse(
            content="<html><body><h1>Not Available</h1>"
            "<p>Email confirmation is handled locally in this deployment.</p>"
            "</body></html>",
            status_code=200,
        )

    supabase_url = settings.SUPABASE_URL
    supabase_anon_key = settings.SUPABASE_ANON_KEY

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IAMS</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif; color:#1a1a1a; }}
    .page {{ max-width:480px; margin:0 auto; padding:80px 24px; text-align:center; }}
    .logo {{ font-size:28px; font-weight:700; letter-spacing:2px; margin-bottom:48px; }}
    .icon {{ width:64px; height:64px; margin:0 auto 24px; border-radius:50%; display:flex; align-items:center; justify-content:center; }}
    .icon-success {{ background:#f0fdf4; }}
    .icon-key {{ background:#f0f4ff; }}
    h1 {{ font-size:22px; font-weight:600; margin-bottom:12px; }}
    .subtitle {{ font-size:15px; color:#6b7280; line-height:1.6; margin-bottom:32px; }}
    .footer {{ font-size:12px; color:#d1d5db; margin-top:48px; }}
    .form-group {{ text-align:left; margin-bottom:16px; }}
    label {{ display:block; font-size:13px; font-weight:500; color:#374151; margin-bottom:6px; }}
    input {{ width:100%; padding:12px 16px; font-size:15px; border:1.5px solid #e5e7eb; border-radius:8px; outline:none; transition:border-color 0.15s; }}
    input:focus {{ border-color:#1a1a1a; }}
    .btn {{ display:inline-block; width:100%; padding:14px; font-size:15px; font-weight:600; border:none; border-radius:8px; cursor:pointer; transition:opacity 0.15s; }}
    .btn-primary {{ background:#1a1a1a; color:#fff; }}
    .btn-primary:hover {{ opacity:0.9; }}
    .btn-primary:disabled {{ opacity:0.5; cursor:not-allowed; }}
    .error-text {{ color:#dc2626; font-size:13px; margin-top:8px; }}
    .success-msg {{ color:#16a34a; font-size:15px; }}
    .hint {{ font-size:13px; color:#9ca3af; margin-top:8px; }}
    .hidden {{ display:none; }}
  </style>
</head>
<body>
  <div class="page">
    <div class="logo">IAMS</div>

    <!-- Email Verified View -->
    <div id="view-verified" class="hidden">
      <div class="icon icon-success">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
      <h1>Email Verified</h1>
      <p class="subtitle">Your email has been confirmed. Return to the IAMS app to sign in.</p>
    </div>

    <!-- Password Reset View -->
    <div id="view-reset" class="hidden">
      <div class="icon icon-key">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      </div>
      <h1>Reset Your Password</h1>
      <p class="subtitle">Enter your new password below.</p>

      <form id="reset-form" onsubmit="return handleReset(event)">
        <div class="form-group">
          <label for="password">New Password</label>
          <input type="password" id="password" placeholder="At least 8 characters" minlength="8" required />
        </div>
        <div class="form-group">
          <label for="confirm">Confirm Password</label>
          <input type="password" id="confirm" placeholder="Re-enter your password" minlength="8" required />
        </div>
        <div id="form-error" class="error-text hidden"></div>
        <button type="submit" id="submit-btn" class="btn btn-primary" style="margin-top:24px;">Update Password</button>
      </form>
    </div>

    <!-- Password Reset Success View -->
    <div id="view-reset-success" class="hidden">
      <div class="icon icon-success">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
      <h1>Password Updated</h1>
      <p class="subtitle">Your password has been changed successfully. Return to the IAMS app to sign in.</p>
    </div>

    <!-- Loading View -->
    <div id="view-loading">
      <p class="subtitle">Loading...</p>
    </div>

    <p class="footer">&copy; 2026 IAMS. All rights reserved.</p>
  </div>

  <script>
    const SUPABASE_URL = '{supabase_url}';
    const SUPABASE_ANON_KEY = '{supabase_anon_key}';
    let accessToken = null;

    function parseHash() {{
      const hash = window.location.hash.substring(1);
      const params = new URLSearchParams(hash);
      return {{
        type: params.get('type'),
        accessToken: params.get('access_token'),
      }};
    }}

    function showView(id) {{
      document.querySelectorAll('[id^="view-"]').forEach(el => el.classList.add('hidden'));
      document.getElementById(id).classList.remove('hidden');
    }}

    function showError(msg) {{
      const el = document.getElementById('form-error');
      el.textContent = msg;
      el.classList.remove('hidden');
    }}

    function hideError() {{
      document.getElementById('form-error').classList.add('hidden');
    }}

    async function handleReset(e) {{
      e.preventDefault();
      hideError();

      const password = document.getElementById('password').value;
      const confirm = document.getElementById('confirm').value;

      if (password.length < 8) {{
        showError('Password must be at least 8 characters.');
        return false;
      }}
      if (password !== confirm) {{
        showError('Passwords do not match.');
        return false;
      }}

      const btn = document.getElementById('submit-btn');
      btn.disabled = true;
      btn.textContent = 'Updating...';

      try {{
        const res = await fetch(SUPABASE_URL + '/auth/v1/user', {{
          method: 'PUT',
          headers: {{
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + accessToken,
            'apikey': SUPABASE_ANON_KEY,
          }},
          body: JSON.stringify({{ password: password }}),
        }});

        if (!res.ok) {{
          const data = await res.json().catch(() => ({{}}));
          throw new Error(data.msg || data.error_description || 'Failed to update password');
        }}

        showView('view-reset-success');
      }} catch (err) {{
        showError(err.message || 'Something went wrong. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Update Password';
      }}

      return false;
    }}

    // Route to the correct view on page load
    (function() {{
      const {{ type, accessToken: token }} = parseHash();
      accessToken = token;

      if (type === 'recovery' && token) {{
        showView('view-reset');
      }} else {{
        showView('view-verified');
      }}
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


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
    if not settings.USE_SUPABASE_AUTH:
        return {"success": True, "message": "Supabase Auth disabled; webhook ignored"}

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
