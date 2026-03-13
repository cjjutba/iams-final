"""
Schedule Model

Represents class schedules (when and where classes meet).
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Schedule(Base):
    """
    Schedule model

    Represents a class schedule (subject, time, location, faculty).

    Attributes:
        id: UUID primary key
        subject_code: Subject code (e.g., "CPE301")
        subject_name: Subject name (e.g., "Microprocessors")
        faculty_id: Foreign key to faculty user
        room_id: Foreign key to room
        day_of_week: Day of week (0=Monday, 6=Sunday)
        start_time: Class start time
        end_time: Class end time
        semester: Semester (e.g., "1st", "2nd")
        academic_year: Academic year (e.g., "2024-2025")
        is_active: Whether the schedule is active
    """

    __tablename__ = "schedules"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Subject details
    subject_code = Column(String(20), nullable=False, index=True)
    subject_name = Column(String(200), nullable=False)

    # Foreign keys
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, index=True)

    # Schedule details
    day_of_week = Column(Integer, nullable=False)  # 0-6 (Monday-Sunday)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # Academic period
    semester = Column(String(20), nullable=False)  # "1st", "2nd", "Summer"
    academic_year = Column(String(20), nullable=False)  # "2024-2025"

    # Target audience (for auto-enrollment matching)
    target_course = Column(String(100), nullable=True, index=True)  # e.g., "BSCPE"
    target_year_level = Column(Integer, nullable=True)  # e.g., 4

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    faculty = relationship("User", foreign_keys=[faculty_id], backref="teaching_schedules")
    room = relationship("Room", backref="schedules")
    # enrollments = relationship("Enrollment", back_populates="schedule")
    # attendance_records = relationship("AttendanceRecord", back_populates="schedule")

    # Indexes
    __table_args__ = (
        Index("idx_schedule_day_time", "day_of_week", "start_time"),
        Index("idx_schedule_target", "target_course", "target_year_level"),
    )

    def __repr__(self):
        return f"<Schedule(id={self.id}, subject={self.subject_code}, day={self.day_of_week})>"
