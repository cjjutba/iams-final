"""
User Repository

Data access layer for User operations.
"""

import uuid as uuid_mod

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.utils.exceptions import DuplicateError, NotFoundError


class UserRepository:
    """Repository for User CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID"""
        if isinstance(user_id, str):
            user_id = uuid_mod.UUID(user_id)
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_student_id(self, student_id: str) -> User | None:
        """Get user by student ID"""
        return self.db.query(User).filter(User.student_id == student_id).first()

    def get_by_student_id_or_email(self, student_id: str, email: str) -> User | None:
        """Check if a user exists with the given student_id or email (single query)."""
        return self.db.query(User).filter(or_(User.student_id == student_id, User.email == email)).first()

    def get_by_identifier(self, identifier: str) -> User | None:
        """
        Get user by email or student ID

        Args:
            identifier: Email or student ID

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(or_(User.email == identifier, User.student_id == identifier)).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all users with pagination"""
        return self.db.query(User).offset(skip).limit(limit).all()

    def get_by_role(self, role: UserRole, skip: int = 0, limit: int = 100) -> list[User]:
        """Get users by role"""
        return self.db.query(User).filter(User.role == role).offset(skip).limit(limit).all()

    def get_students_by_schedule(self, schedule_id: str) -> list[User]:
        """
        Get all students enrolled in a schedule

        Args:
            schedule_id: Schedule UUID

        Returns:
            List of student users
        """
        from app.models.enrollment import Enrollment

        return (
            self.db.query(User)
            .join(Enrollment, Enrollment.student_id == User.id)
            .filter(Enrollment.schedule_id == schedule_id, User.role == UserRole.STUDENT)
            .all()
        )

    def create(self, user_data: dict) -> User:
        """
        Create new user

        Args:
            user_data: User data dictionary

        Returns:
            Created user

        Raises:
            DuplicateError: If email or student_id already exists
        """
        # Check for duplicates
        if user_data.get("email"):
            existing = self.get_by_email(user_data["email"])
            if existing:
                raise DuplicateError(f"Email already exists: {user_data['email']}")

        if user_data.get("student_id"):
            existing = self.get_by_student_id(user_data["student_id"])
            if existing:
                raise DuplicateError(f"Student ID already exists: {user_data['student_id']}")

        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id: str, update_data: dict) -> User:
        """
        Update user

        Args:
            user_id: User UUID
            update_data: Fields to update

        Returns:
            Updated user

        Raises:
            NotFoundError: If user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        for key, value in update_data.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id: str) -> bool:
        """
        Delete user (soft delete by setting is_active=False)

        Args:
            user_id: User UUID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        user.is_active = False
        self.db.commit()
        return True

    def count(self) -> int:
        """Get total user count"""
        return self.db.query(User).count()

    def count_by_role(self, role: UserRole) -> int:
        """Get user count by role"""
        return self.db.query(User).filter(User.role == role).count()
