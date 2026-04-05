"""
User Service

Business logic for user management operations.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.config import logger
from app.models.student_record import StudentRecord  # noqa: TCH001
from app.models.user import User, UserRole
from app.repositories.student_record_repository import StudentRecordRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import AdminCreateUser
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.security import hash_password


class UserService:
    """Service for user management operations"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.student_record_repo = StudentRecordRepository(db)

    def get_user(self, user_id: str) -> User:
        """
        Get user by ID

        Args:
            user_id: User UUID

        Returns:
            User object

        Raises:
            NotFoundError: If user not found
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")
        return user

    def get_user_by_email(self, email: str) -> User:
        """
        Get user by email

        Args:
            email: User email

        Returns:
            User object

        Raises:
            NotFoundError: If user not found
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            raise NotFoundError(f"User not found with email: {email}")
        return user

    def get_user_by_student_id(self, student_id: str) -> User:
        """
        Get user by student ID

        Args:
            student_id: Student ID

        Returns:
            User object

        Raises:
            NotFoundError: If user not found
        """
        user = self.user_repo.get_by_student_id(student_id)
        if not user:
            raise NotFoundError(f"User not found with student ID: {student_id}")
        return user

    def get_all_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """
        Get all users with pagination

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of users
        """
        return self.user_repo.get_all(skip, limit)

    def get_users_by_role(self, role: UserRole, skip: int = 0, limit: int = 100) -> list[User]:
        """
        Get users by role

        Args:
            role: User role
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of users with specified role
        """
        return self.user_repo.get_by_role(role, skip, limit)

    def update_user(self, user_id: str, update_data: dict) -> User:
        """
        Update user information

        Args:
            user_id: User UUID
            update_data: Fields to update

        Returns:
            Updated user

        Raises:
            NotFoundError: If user not found
            ValidationError: If update data is invalid
        """
        # Validate update data
        if "email" in update_data and not update_data["email"]:
            raise ValidationError("Email cannot be empty")

        if "first_name" in update_data and not update_data["first_name"]:
            raise ValidationError("First name cannot be empty")

        if "last_name" in update_data and not update_data["last_name"]:
            raise ValidationError("Last name cannot be empty")

        # Update user
        user = self.user_repo.update(user_id, update_data)
        logger.info(f"User updated: {user.email}")
        return user

    def deactivate_user(self, user_id: str) -> bool:
        """
        Deactivate user account

        Args:
            user_id: User UUID

        Returns:
            True if deactivated

        Raises:
            NotFoundError: If user not found
        """
        success = self.user_repo.delete(user_id)
        if success:
            logger.info(f"User deactivated: {user_id}")
        return success

    def reactivate_user(self, user_id: str) -> User:
        """
        Reactivate user account

        Args:
            user_id: User UUID

        Returns:
            Reactivated user

        Raises:
            NotFoundError: If user not found
        """
        user = self.user_repo.update(user_id, {"is_active": True})
        logger.info(f"User reactivated: {user.email}")
        return user

    def admin_create_user(self, body: AdminCreateUser) -> User:
        """
        Admin-initiated user creation for faculty/admin only.
        Students are added via create_student_record instead.
        """
        if body.role == UserRole.STUDENT:
            raise ValidationError("Use the student-records endpoint to add students")

        # Check for duplicate email
        existing = self.user_repo.get_by_email(body.email)
        if existing:
            raise ValidationError(f"An account with email {body.email} already exists")

        # Build user data
        user_data = {
            "email": body.email,
            "first_name": body.first_name,
            "last_name": body.last_name,
            "phone": body.phone,
            "role": body.role,
            "is_active": True,
            "email_verified": True,  # Admin-created accounts are pre-verified
        }

        user_data["password_hash"] = hash_password(body.password)

        user = self.user_repo.create(user_data)
        logger.info(f"Admin created {body.role} user: {user.email}")
        return user

    def get_student_records_with_status(self, skip: int = 0, limit: int = 1000) -> list[dict]:
        """Get all student records with app registration status."""
        return self.student_record_repo.get_all_with_status(skip, limit)

    def get_student_record(self, student_id: str) -> dict:
        """Get a single student record with registration status."""
        from app.models.face_registration import FaceRegistration

        normalized = student_id.strip().upper()
        record = self.student_record_repo.get_by_student_id(normalized)
        if not record:
            raise NotFoundError(f"Student record not found: {student_id}")

        user = self.user_repo.get_by_student_id(normalized)
        has_face = False
        if user:
            face = (
                self.db.query(FaceRegistration)
                .filter(FaceRegistration.user_id == user.id, FaceRegistration.is_active == True)
                .first()
            )
            has_face = face is not None

        return {
            "record": record,
            "user_id": str(user.id) if user else None,
            "is_registered": user is not None,
            "has_face_registered": has_face,
        }

    def update_student_record(self, student_id: str, update_data: dict) -> "StudentRecord":
        """Update a student record."""

        normalized = student_id.strip().upper()
        if "birthdate" in update_data and update_data["birthdate"]:
            update_data["birthdate"] = date.fromisoformat(update_data["birthdate"])

        record = self.student_record_repo.update(normalized, update_data)
        self.db.commit()
        logger.info(f"Updated student record: {normalized}")
        return record

    def deactivate_student_record(self, student_id: str) -> bool:
        """Deactivate a student record."""
        normalized = student_id.strip().upper()
        result = self.student_record_repo.deactivate(normalized)
        self.db.commit()
        logger.info(f"Deactivated student record: {normalized}")
        return result

    def create_student_record(self, body) -> "StudentRecord":
        """
        Create a student record in the student_records registry.
        The student can then self-register via the mobile app.
        """

        normalized_id = body.student_id.strip().upper()

        # Check for duplicate
        existing = self.student_record_repo.get_by_student_id(normalized_id)
        if existing:
            raise ValidationError(f"Student ID {normalized_id} already exists in the registry")

        record_data = {
            "student_id": normalized_id,
            "first_name": body.first_name,
            "middle_name": body.middle_name,
            "last_name": body.last_name,
            "email": body.email,
            "course": body.course,
            "year_level": body.year_level,
            "section": body.section,
            "contact_number": body.contact_number,
            "is_active": True,
        }
        if body.birthdate:
            record_data["birthdate"] = date.fromisoformat(body.birthdate)

        record = self.student_record_repo.create(record_data)
        self.db.commit()
        logger.info(f"Admin created student record: {normalized_id}")
        return record

    def get_statistics(self) -> dict:
        """
        Get user statistics

        Returns:
            Dictionary with user counts by role
        """
        return {
            "total_users": self.user_repo.count(),
            "students": self.user_repo.count_by_role(UserRole.STUDENT),
            "faculty": self.user_repo.count_by_role(UserRole.FACULTY),
            "admins": self.user_repo.count_by_role(UserRole.ADMIN),
        }
