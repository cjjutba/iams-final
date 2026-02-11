"""
User Model

Represents all system users: students, faculty, and admins.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
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
    password_hash = Column(String(255), nullable=True)  # Nullable when using Supabase Auth
    supabase_user_id = Column(UUID(as_uuid=True), unique=True, nullable=True, index=True)

    # Profile
    role = Column(SQLEnum(UserRole), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)

    # Student-specific
    student_id = Column(String(50), unique=True, nullable=True, index=True)

    # Email verification
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships (will be defined when other models are created)
    # face_registration = relationship("FaceRegistration", back_populates="user", uselist=False)
    # schedules = relationship("Schedule", back_populates="faculty")  # For faculty
    # enrollments = relationship("Enrollment", back_populates="student")  # For students
    # attendance_records = relationship("AttendanceRecord", back_populates="student")  # For students

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    @property
    def full_name(self) -> str:
        """Return user's full name"""
        return f"{self.first_name} {self.last_name}"
