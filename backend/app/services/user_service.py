"""
User Service

Business logic for user management operations.
"""

from sqlalchemy.orm import Session

from app.config import logger
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import NotFoundError, ValidationError


class UserService:
    """Service for user management operations"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

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
