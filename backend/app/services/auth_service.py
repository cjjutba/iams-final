"""
Authentication Service

Business logic for authentication and authorization.
Supports dual mode: custom JWT (legacy) and Supabase Auth.
"""

import uuid as uuid_mod
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.repositories.student_record_repository import StudentRecordRepository
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    validate_password_strength
)
from app.utils.exceptions import (
    AuthenticationError,
    ValidationError,
    NotFoundError
)
from app.config import settings, logger


class AuthService:
    """Service for authentication operations"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.student_record_repo = StudentRecordRepository(db)

    # ------------------------------------------------------------------
    # FUN-01-01: Verify Student Identity
    # ------------------------------------------------------------------

    def verify_student_id(self, student_id: str, birthdate: datetime) -> dict:
        """
        Verify student ID and birthdate against the student_records reference table.

        Two-factor verification:
          1. Student ID must exist in university database
          2. Birthdate must match the official record

        This prevents unauthorized users from viewing student information by
        entering random student IDs.

        Args:
            student_id: Student ID to verify (e.g. "21-A-02177")
            birthdate: Student's birthdate for identity verification

        Returns:
            Dictionary with validation result and student info (only if both match)
        """
        logger.info(f"Verifying student ID: {student_id}")

        if not student_id or len(student_id.strip()) < 3:
            return {
                "valid": False,
                "student_info": None,
                "message": "Invalid student ID format"
            }

        normalized = student_id.strip().upper()

        # Look up in the school's official registry
        record = self.student_record_repo.get_by_student_id(normalized)

        if not record:
            logger.warning(f"Student ID not found in registry: {normalized}")
            return {
                "valid": False,
                "student_info": None,
                "message": "Student ID not found in university records"
            }

        if not record.is_active:
            return {
                "valid": False,
                "student_info": None,
                "message": "Student ID is no longer active"
            }

        # SECURITY: Verify birthdate matches before showing student information
        if not record.birthdate:
            logger.error(f"Student record missing birthdate: {normalized}")
            return {
                "valid": False,
                "student_info": None,
                "message": "Unable to verify identity. Please contact registrar."
            }

        # Convert datetime to date if needed
        verification_date = birthdate.date() if isinstance(birthdate, datetime) else birthdate

        if record.birthdate != verification_date:
            logger.warning(f"Birthdate mismatch for {normalized}")
            return {
                "valid": False,
                "student_info": None,
                "message": "Identity verification failed. Please check your birthdate."
            }

        # Reject if already has an app account (prevent duplicate registration)
        existing_user = self.user_repo.get_by_student_id(normalized)
        if existing_user:
            return {
                "valid": False,
                "student_info": None,
                "message": "This student ID is already registered. Please login instead."
            }

        # Both student ID and birthdate verified — return student info
        return {
            "valid": True,
            "student_info": {
                "student_id": record.student_id,
                "first_name": record.first_name,
                "last_name": record.last_name,
                "course": record.course,
                "year": record.year_level,
                "section": record.section,
                "email": record.email,
                "contact_number": record.contact_number,
            },
            "message": "Student ID verified successfully"
        }

    # ------------------------------------------------------------------
    # FUN-01-02: Register Student Account
    # ------------------------------------------------------------------

    def register_student(self, registration_data: dict) -> Tuple[User, dict]:
        """
        Register a new student account.

        When USE_SUPABASE_AUTH is enabled the flow is:
            1. Validate student ID against school registry
            2. Validate password strength
            3. Create user in Supabase Auth (triggers email verification)
            4. Create local user record linked via supabase_user_id

        When USE_SUPABASE_AUTH is disabled (legacy):
            1-2. Same as above
            3. Hash password locally
            4. Create user record with password_hash
            5. Return custom JWT tokens

        Args:
            registration_data: Registration data from request

        Returns:
            Tuple of (created user, response dict with tokens or message)
        """
        # Validate student ID exists in school registry
        # Note: Full verification (ID + birthdate) already done in Step 1 of registration flow.
        # Here we just validate that the student exists and is not already registered.
        normalized_id = registration_data["student_id"].strip().upper()

        record = self.student_record_repo.get_by_student_id(normalized_id)
        if not record:
            raise ValidationError("Student ID not found in university records")

        if not record.is_active:
            raise ValidationError("Student ID is no longer active")

        # Check if already registered
        existing_user = self.user_repo.get_by_student_id(normalized_id)
        if existing_user:
            raise ValidationError("This student ID is already registered. Please login instead.")

        # Validate password strength
        is_valid, error_msg = validate_password_strength(registration_data["password"])
        if not is_valid:
            raise ValidationError(error_msg)

        # Use official name from student_records (prevents tampering)
        # record is already fetched above

        if settings.USE_SUPABASE_AUTH:
            return self._register_student_supabase(registration_data, record, normalized_id)
        else:
            return self._register_student_legacy(registration_data, record, normalized_id)

    def _register_student_supabase(self, registration_data: dict, record, normalized_id: str) -> Tuple[User, dict]:
        """Create student via Supabase Auth Admin API."""
        from app.services.supabase_client import get_supabase_admin

        supabase = get_supabase_admin()

        # Create user in Supabase Auth (email_confirm=False → sends verification email)
        try:
            sb_response = supabase.auth.admin.create_user({
                "email": registration_data["email"],
                "password": registration_data["password"],
                "email_confirm": False,
                "user_metadata": {
                    "first_name": record.first_name,
                    "last_name": record.last_name,
                    "student_id": normalized_id,
                    "role": "student",
                },
            })
            supabase_user = sb_response.user
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Supabase user creation failed: {error_msg}")
            if "already been registered" in error_msg.lower() or "duplicate" in error_msg.lower():
                from app.utils.exceptions import DuplicateError
                raise DuplicateError("An account with this email already exists")
            raise ValidationError(f"Failed to create account: {error_msg}")

        # Create local user record
        user_data = {
            "email": registration_data["email"],
            "password_hash": None,  # Managed by Supabase
            "role": UserRole.STUDENT,
            "first_name": record.first_name,
            "last_name": record.last_name,
            "student_id": normalized_id,
            "phone": registration_data.get("phone"),
            "is_active": True,
            "email_verified": False,
            "supabase_user_id": uuid_mod.UUID(supabase_user.id),
        }

        user = self.user_repo.create(user_data)

        logger.info(f"Student registered via Supabase Auth: {user.email}")
        return user, {
            "message": "Account created. Please check your email to verify your address.",
        }

    def _register_student_legacy(self, registration_data: dict, record, normalized_id: str) -> Tuple[User, dict]:
        """Create student with local password hashing (legacy / custom JWT mode)."""
        user_data = {
            "email": registration_data["email"],
            "password_hash": hash_password(registration_data["password"]),
            "role": UserRole.STUDENT,
            "first_name": record.first_name,
            "last_name": record.last_name,
            "student_id": normalized_id,
            "phone": registration_data.get("phone"),
            "is_active": True,
            "email_verified": True,  # Legacy mode: skip email verification
        }

        user = self.user_repo.create(user_data)
        tokens = self._generate_tokens(user)

        logger.info(f"Student registered (legacy): {user.email}")
        return user, tokens

    # ------------------------------------------------------------------
    # FUN-01-03: Login (custom JWT — kept for dual-auth)
    # ------------------------------------------------------------------

    def login(self, identifier: str, password: str) -> Tuple[User, dict]:
        """
        Authenticate user and generate tokens (custom JWT mode).

        When USE_SUPABASE_AUTH is True, login is handled by the mobile
        Supabase SDK (signInWithPassword). This method remains for
        backward compatibility and the dual-auth transition.

        Args:
            identifier: Email or student ID
            password: Plain text password

        Returns:
            Tuple of (user, tokens)
        """
        user = self.user_repo.get_by_identifier(identifier)

        if not user:
            logger.warning(f"Login failed: User not found for identifier {identifier}")
            raise AuthenticationError("Invalid email/student ID or password")

        if not user.password_hash:
            raise AuthenticationError(
                "This account uses Supabase Auth. Please login via the mobile app."
            )

        if not verify_password(password, user.password_hash):
            logger.warning(f"Login failed: Invalid password for user {user.id}")
            raise AuthenticationError("Invalid email/student ID or password")

        if not user.is_active:
            logger.warning(f"Login failed: User {user.id} is inactive")
            raise AuthenticationError("User account is inactive")

        tokens = self._generate_tokens(user)

        logger.info(f"User logged in successfully: {user.email}")
        return user, tokens

    # ------------------------------------------------------------------
    # FUN-01-04: Refresh Token (custom JWT)
    # ------------------------------------------------------------------

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Generate new access token from refresh token (custom JWT mode).

        When USE_SUPABASE_AUTH is True, refresh is handled automatically
        by the Supabase client SDK.
        """
        from app.utils.security import verify_token

        try:
            payload = verify_token(refresh_token)

            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")

            user_id = payload.get("user_id")
            if not user_id:
                raise AuthenticationError("Invalid token payload")

            user = self.user_repo.get_by_id(user_id)
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            access_token = create_access_token({"user_id": str(user.id)})

            return {
                "access_token": access_token,
                "token_type": "bearer"
            }

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError("Invalid or expired refresh token")

    # ------------------------------------------------------------------
    # FUN-01-05: Get Current User (handled by dependency in dependencies.py)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # FUN-01-06: Request Password Reset
    # ------------------------------------------------------------------

    def forgot_password(self, email: str) -> dict:
        """
        Handle forgot password request.

        When USE_SUPABASE_AUTH is True, delegates to Supabase Auth
        to generate a password recovery link and send the email.

        Always returns a success response to prevent email enumeration.

        Args:
            email: User email address

        Returns:
            Dictionary with success message
        """
        success_msg = "If an account with that email exists, a password reset link has been sent."

        if settings.USE_SUPABASE_AUTH:
            try:
                from app.services.supabase_client import get_supabase_admin
                supabase = get_supabase_admin()

                supabase.auth.admin.generate_link({
                    "type": "recovery",
                    "email": email,
                })
                logger.info(f"Password reset link generated for: {email}")
            except Exception as e:
                # Don't reveal whether the email exists
                logger.warning(f"Password reset generation failed (may be unknown email): {e}")
        else:
            # Legacy mode: log the request
            user = self.user_repo.get_by_email(email)
            if not user:
                logger.warning(f"Password reset requested for unknown email: {email}")
            else:
                logger.info(f"Password reset requested for user: {email}")

        return {
            "success": True,
            "message": success_msg,
        }

    # ------------------------------------------------------------------
    # Email Verification helpers
    # ------------------------------------------------------------------

    def handle_email_verified(self, supabase_user_id: str) -> Optional[User]:
        """
        Mark a user's email as verified.

        Called from the Supabase webhook handler when Supabase Auth
        confirms the user's email.

        Args:
            supabase_user_id: The Supabase Auth user UUID

        Returns:
            Updated user or None if not found
        """
        try:
            sb_uuid = uuid_mod.UUID(supabase_user_id)
        except ValueError:
            logger.error(f"Invalid supabase_user_id: {supabase_user_id}")
            return None

        user = (
            self.db.query(User)
            .filter(User.supabase_user_id == sb_uuid)
            .first()
        )

        if not user:
            logger.warning(f"Webhook: no local user for supabase_user_id {supabase_user_id}")
            return None

        user.email_verified = True
        user.email_verified_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)

        logger.info(f"Email verified for user {user.email}")
        return user

    def resend_verification_email(self, email: str) -> dict:
        """
        Resend the email verification link.

        Uses Supabase Admin API to re-send the sign-up confirmation email.
        Always returns success to prevent email enumeration.
        """
        success_msg = "If an account with that email exists, a verification email has been sent."

        if not settings.USE_SUPABASE_AUTH:
            return {"success": True, "message": success_msg}

        try:
            from app.services.supabase_client import get_supabase_admin
            supabase = get_supabase_admin()

            supabase.auth.admin.generate_link({
                "type": "signup",
                "email": email,
            })
            logger.info(f"Verification email re-sent to: {email}")
        except Exception as e:
            logger.warning(f"Resend verification failed: {e}")

        return {"success": True, "message": success_msg}

    # ------------------------------------------------------------------
    # Password & Profile management
    # ------------------------------------------------------------------

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """
        Change user password.

        When USE_SUPABASE_AUTH is True and the user has a supabase_user_id,
        the password is also updated in Supabase Auth.
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        # Verify old password (only for users with local password)
        if user.password_hash:
            if not verify_password(old_password, user.password_hash):
                raise AuthenticationError("Current password is incorrect")

        # Validate new password
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise ValidationError(error_msg)

        # Update local password hash
        self.user_repo.update(user_id, {
            "password_hash": hash_password(new_password)
        })

        # Also update in Supabase Auth if applicable
        if settings.USE_SUPABASE_AUTH and user.supabase_user_id:
            try:
                from app.services.supabase_client import get_supabase_admin
                supabase = get_supabase_admin()
                supabase.auth.admin.update_user_by_id(
                    str(user.supabase_user_id),
                    {"password": new_password},
                )
            except Exception as e:
                logger.error(f"Failed to update Supabase password: {e}")

        logger.info(f"Password changed for user: {user.email}")
        return True

    def update_profile(self, user_id: str, update_data: dict) -> User:
        """
        Update user profile (self-service, limited fields)
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        allowed_fields = {"email", "phone"}
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields and v is not None}

        if not filtered_data:
            raise ValidationError("No valid fields to update")

        # Check for email uniqueness if email is being changed
        if "email" in filtered_data and filtered_data["email"] != user.email:
            existing = self.user_repo.get_by_email(filtered_data["email"])
            if existing:
                from app.utils.exceptions import DuplicateError
                raise DuplicateError(f"Email already in use: {filtered_data['email']}")

        updated_user = self.user_repo.update(user_id, filtered_data)
        logger.info(f"Profile updated for user: {updated_user.email}")
        return updated_user

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_tokens(self, user: User) -> dict:
        """Generate access and refresh tokens (custom JWT)."""
        access_token = create_access_token({"user_id": str(user.id)})
        refresh_token = create_refresh_token({"user_id": str(user.id)})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
