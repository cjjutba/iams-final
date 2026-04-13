"""
User Model

Represents all system users: students, faculty, and admins.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(enum.StrEnum):
    """User role enumeration"""

    STUDENT = "student"
    FACULTY = "faculty"
    ADMIN = "admin"


class User(Base):
    """
    User model for all system users

    Attributes:
        id: UUID primary key
        email: Unique email address
        password_hash: Hashed password (bcrypt)
        role: User role (student, faculty, admin)
        first_name: User's first name
        last_name: User's last name
        phone: Phone number (optional)
        student_id: Student ID (required for students, unique)
        is_active: Whether the account is active
        created_at: Timestamp of account creation
        updated_at: Timestamp of last update
    """

    __tablename__ = "users"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    role = Column(SQLEnum(UserRole), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)

    # Student-specific
    student_id = Column(String(50), unique=True, nullable=True, index=True)

    # Supabase integration
    supabase_user_id = Column(String(255), unique=True, nullable=True, index=True)

    # Email verification
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), nullable=False)

    # Relationships
    face_registration = relationship("FaceRegistration", back_populates="user", uselist=False)
    teaching_schedules = relationship("Schedule", back_populates="faculty", foreign_keys="[Schedule.faculty_id]")
    enrollments = relationship("Enrollment", back_populates="student", foreign_keys="[Enrollment.student_id]")
    attendance_records = relationship(
        "AttendanceRecord", back_populates="student", foreign_keys="[AttendanceRecord.student_id]"
    )
    notifications = relationship("Notification", back_populates="user", foreign_keys="[Notification.user_id]")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    @property
    def full_name(self) -> str:
        """Return user's full name"""
        return f"{self.first_name} {self.last_name}"
