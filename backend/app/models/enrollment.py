"""
Enrollment Model

Links students to the classes they are enrolled in.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Enrollment(Base):
    """
    Enrollment model

    Represents a student's enrollment in a specific class schedule.

    Attributes:
        id: UUID primary key
        student_id: Foreign key to student user
        schedule_id: Foreign key to schedule
        enrolled_at: Timestamp of enrollment
    """

    __tablename__ = "enrollments"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timestamp
    enrolled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], back_populates="enrollments")
    schedule = relationship("Schedule", back_populates="enrollments")

    # Unique constraint (one enrollment per student per schedule)
    __table_args__ = (UniqueConstraint("student_id", "schedule_id", name="uq_student_schedule"),)

    def __repr__(self):
        return f"<Enrollment(id={self.id}, student_id={self.student_id}, schedule_id={self.schedule_id})>"
