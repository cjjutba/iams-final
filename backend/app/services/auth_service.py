"""
Authentication Service

Business logic for authentication and authorization.
Uses local JWT authentication with bcrypt password hashing.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import logger
from app.models.user import User, UserRole
from app.repositories.student_record_repository import StudentRecordRepository
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


class AuthService:
    """Service for authentication operations"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.student_record_repo = StudentRecordRepository(db)

    # ------------------------------------------------------------------
    # FUN-01-01a: Check Student ID Availability
    # ------------------------------------------------------------------

    def check_student_id(self, student_id: str) -> dict:
        """
        Check if a student ID exists in university records and is available
        for registration (not already registered).

        Args:
            student_id: Student ID to check (e.g. "21-A-01234")

        Returns:
            Dictionary with exists, available, and message fields
        """
        if not student_id or len(student_id.strip()) < 3:
            return {"exists": False, "available": False, "message": "Invalid student ID format"}

        normalized = student_id.strip().upper()

        record = self.student_record_repo.get_by_student_id(normalized)
        if not record:
            return {"exists": False, "available": False, "message": "Student ID not found in university records"}

        if not record.is_active:
            return {"exists": True, "available": False, "message": "Student ID is no longer active"}

        existing_user = self.user_repo.get_by_student_id(normalized)
        if existing_user:
            return {"exists": True, "available": False, "message": "This student ID is already registered. Please login instead."}

        return {"exists": True, "available": True, "message": "Student ID found"}

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
            student_id: Student ID to verify (e.g. "21-A-012345")
            birthdate: Student's birthdate for identity verification

        Returns:
            Dictionary with validation result and student info (only if both match)
        """
        logger.info(f"Verifying student ID: {student_id}")

        if not student_id or len(student_id.strip()) < 3:
            return {"valid": False, "student_info": None, "message": "Invalid student ID format"}

        normalized = student_id.strip().upper()

        # Look up in the school's official registry
        record = self.student_record_repo.get_by_student_id(normalized)

        if not record:
            logger.warning(f"Student ID not found in registry: {normalized}")
            return {"valid": False, "student_info": None, "message": "Student ID not found in university records"}

        if not record.is_active:
            return {"valid": False, "student_info": None, "message": "Student ID is no longer active"}

        # SECURITY: Verify birthdate matches before showing student information
        if not record.birthdate:
            logger.error(f"Student record missing birthdate: {normalized}")
            return {
                "valid": False,
                "student_info": None,
                "message": "Unable to verify identity. Please contact registrar.",
            }

        # Convert datetime to date if needed
        verification_date = birthdate.date() if isinstance(birthdate, datetime) else birthdate

        if record.birthdate != verification_date:
            logger.warning(f"Birthdate mismatch for {normalized}")
            return {
                "valid": False,
                "student_info": None,
                "message": "Identity verification failed. Please check your birthdate.",
            }

        # Reject if already has an app account (prevent duplicate registration)
        existing_user = self.user_repo.get_by_student_id(normalized)
        if existing_user:
            return {
                "valid": False,
                "student_info": None,
                "message": "This student ID is already registered. Please login instead.",
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
            "message": "Student ID verified successfully",
        }

    # ------------------------------------------------------------------
    # FUN-01-02: Register Student Account
    # ------------------------------------------------------------------

    def register_student(self, registration_data: dict) -> tuple[User, dict]:
        """
        Register a new student account.

        Flow:
            1. Validate student ID against school registry
            2. Validate password strength
            3. Hash password locally
            4. Create user record with password_hash
            5. Auto-enroll in matching schedules
            6. Return JWT tokens

        Args:
            registration_data: Registration data from request

        Returns:
            Tuple of (created user, response dict with tokens)
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

        # Check if already registered (student ID or email) in a single query
        existing_user = self.user_repo.get_by_student_id_or_email(normalized_id, registration_data["email"])
        if existing_user:
            if existing_user.student_id == normalized_id:
                raise ValidationError("This student ID is already registered. Please login instead.")
            from app.utils.exceptions import DuplicateError

            raise DuplicateError("An account with this email already exists")

        # Validate password strength
        is_valid, error_msg = validate_password_strength(registration_data["password"])
        if not is_valid:
            raise ValidationError(error_msg)

        # Use official name from student_records (prevents tampering)
        user = User(
            email=registration_data["email"],
            password_hash=hash_password(registration_data["password"]),
            role=UserRole.STUDENT,
            first_name=record.first_name,
            last_name=record.last_name,
            student_id=normalized_id,
            phone=registration_data.get("phone"),
            is_active=True,
            email_verified=True,
        )
        self.db.add(user)
        self.db.flush()

        # Auto-enroll in matching schedules
        from app.services.enrollment_service import EnrollmentService

        enrollment_service = EnrollmentService(self.db)
        enrollment_service.auto_enroll_student(
            user.id,
            normalized_id,
            record=record,
            skip_duplicate_check=True,
        )

        self.db.expire_on_commit = False
        self.db.commit()
        self.db.expire_on_commit = True

        tokens = self._generate_tokens(user)

        logger.info(f"Student registered: {user.email}")
        return user, tokens

    # ------------------------------------------------------------------
    # FUN-01-03: Login
    # ------------------------------------------------------------------

    def login(self, identifier: str, password: str) -> tuple[User, dict]:
        """
        Authenticate user and generate tokens.

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

        if not user.is_active:
            logger.warning(f"Login failed: User {user.id} is inactive")
            raise AuthenticationError("User account is inactive")

        if not verify_password(password, user.password_hash):
            logger.warning(f"Login failed: Invalid password for user {user.id}")
            raise AuthenticationError("Invalid email/student ID or password")

        tokens = self._generate_tokens(user)

        logger.info(f"User logged in successfully: {user.email}")
        return user, tokens

    # ------------------------------------------------------------------
    # FUN-01-04: Refresh Token (custom JWT)
    # ------------------------------------------------------------------

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Generate new access token from refresh token.
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

            return {"access_token": access_token, "token_type": "bearer"}

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError("Invalid or expired refresh token") from e

    # ------------------------------------------------------------------
    # FUN-01-05: Get Current User (handled by dependency in dependencies.py)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # FUN-01-06: Request Password Reset
    # ------------------------------------------------------------------

    def forgot_password(self, email: str) -> dict:
        """
        Handle forgot password request.

        Always returns a success response to prevent email enumeration.

        Args:
            email: User email address

        Returns:
            Dictionary with success message
        """
        success_msg = "If an account with that email exists, a password reset link has been sent."

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
    # Password & Profile management
    # ------------------------------------------------------------------

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """
        Change user password.
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        # Verify old password
        if not verify_password(old_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        # Validate new password
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise ValidationError(error_msg)

        # Update local password hash
        self.user_repo.update(user_id, {"password_hash": hash_password(new_password)})

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

        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
