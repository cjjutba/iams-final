"""
Authentication Service

Business logic for authentication and authorization.
"""

from typing import Tuple
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
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
from app.config import logger


class AuthService:
    """Service for authentication operations"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def verify_student_id(self, student_id: str) -> dict:
        """
        Verify student ID against university database

        For MVP: Accept any non-empty student ID with minimal length.
        In production: Query university database or CSV.

        Args:
            student_id: Student ID to verify

        Returns:
            Dictionary with validation result and student info
        """
        # TODO: Replace with actual university database query
        logger.info(f"Verifying student ID: {student_id}")

        # Reject empty or too-short IDs
        if not student_id or len(student_id.strip()) < 3:
            return {
                "valid": False,
                "student_info": None,
                "message": "Invalid student ID format"
            }

        # For MVP, accept any valid-length student ID.
        # Name details are provided during registration, not verification.
        return {
            "valid": True,
            "student_info": {
                "student_id": student_id.strip(),
            },
            "message": "Student ID verified successfully"
        }

    def register_student(self, registration_data: dict) -> Tuple[User, dict]:
        """
        Register a new student account

        Args:
            registration_data: Registration data from request

        Returns:
            Tuple of (created user, tokens)

        Raises:
            ValidationError: If validation fails
        """
        # Validate student ID first
        verification = self.verify_student_id(registration_data["student_id"])
        if not verification["valid"]:
            raise ValidationError("Invalid student ID")

        # Validate password strength
        is_valid, error_msg = validate_password_strength(registration_data["password"])
        if not is_valid:
            raise ValidationError(error_msg)

        # Create user with name details from registration request
        user_data = {
            "email": registration_data["email"],
            "password_hash": hash_password(registration_data["password"]),
            "role": UserRole.STUDENT,
            "first_name": registration_data["first_name"],
            "last_name": registration_data["last_name"],
            "student_id": registration_data["student_id"],
            "phone": registration_data.get("phone"),
            "is_active": True
        }

        user = self.user_repo.create(user_data)

        # Generate tokens
        tokens = self._generate_tokens(user)

        logger.info(f"Student registered successfully: {user.email}")
        return user, tokens

    def login(self, identifier: str, password: str) -> Tuple[User, dict]:
        """
        Authenticate user and generate tokens

        Args:
            identifier: Email or student ID
            password: Plain text password

        Returns:
            Tuple of (user, tokens)

        Raises:
            AuthenticationError: If authentication fails
        """
        # Find user by email or student ID
        user = self.user_repo.get_by_identifier(identifier)

        if not user:
            logger.warning(f"Login failed: User not found for identifier {identifier}")
            raise AuthenticationError("Invalid email/student ID or password")

        # Verify password
        if not verify_password(password, user.password_hash):
            logger.warning(f"Login failed: Invalid password for user {user.id}")
            raise AuthenticationError("Invalid email/student ID or password")

        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login failed: User {user.id} is inactive")
            raise AuthenticationError("User account is inactive")

        # Generate tokens
        tokens = self._generate_tokens(user)

        logger.info(f"User logged in successfully: {user.email}")
        return user, tokens

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Generate new access token from refresh token

        Args:
            refresh_token: Refresh token

        Returns:
            New access token

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        from app.utils.security import verify_token

        try:
            payload = verify_token(refresh_token)

            # Verify it's a refresh token
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")

            user_id = payload.get("user_id")
            if not user_id:
                raise AuthenticationError("Invalid token payload")

            # Verify user still exists and is active
            user = self.user_repo.get_by_id(user_id)
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            # Generate new access token
            access_token = create_access_token({"user_id": str(user.id)})

            return {
                "access_token": access_token,
                "token_type": "bearer"
            }

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError("Invalid or expired refresh token")

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """
        Change user password

        Args:
            user_id: User UUID
            old_password: Current password
            new_password: New password

        Returns:
            True if password changed successfully

        Raises:
            AuthenticationError: If old password is incorrect
            ValidationError: If new password is invalid
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

        # Update password
        self.user_repo.update(user_id, {
            "password_hash": hash_password(new_password)
        })

        logger.info(f"Password changed for user: {user.email}")
        return True

    def forgot_password(self, email: str) -> dict:
        """
        Handle forgot password request

        For MVP: Log the request and return a success message.
        In production: Send a password reset email with a token.

        Args:
            email: User email address

        Returns:
            Dictionary with success message
        """
        user = self.user_repo.get_by_email(email)

        # Always return success to prevent email enumeration
        if not user:
            logger.warning(f"Password reset requested for unknown email: {email}")
            return {
                "success": True,
                "message": "If an account with that email exists, a password reset link has been sent."
            }

        # TODO: In production, generate a reset token and send via email
        # For MVP, log the request
        logger.info(f"Password reset requested for user: {email}")

        return {
            "success": True,
            "message": "If an account with that email exists, a password reset link has been sent."
        }

    def update_profile(self, user_id: str, update_data: dict) -> User:
        """
        Update user profile (self-service, limited fields)

        Args:
            user_id: User UUID
            update_data: Fields to update (email, phone)

        Returns:
            Updated user

        Raises:
            NotFoundError: If user not found
            DuplicateError: If email already taken
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        # Only allow certain fields to be updated via profile endpoint
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

    def _generate_tokens(self, user: User) -> dict:
        """
        Generate access and refresh tokens

        Args:
            user: User object

        Returns:
            Dictionary with tokens
        """
        access_token = create_access_token({"user_id": str(user.id)})
        refresh_token = create_refresh_token({"user_id": str(user.id)})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
