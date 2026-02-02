"""
Attendance Record Model

Represents daily attendance for a student in a specific class.
"""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, UniqueConstraint, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class AttendanceStatus(str, enum.Enum):
    """Attendance status enumeration"""
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    EARLY_LEAVE = "early_leave"


class AttendanceRecord(Base):
    """
    Attendance record model

    Represents a student's attendance for a single class session.
    Tracks check-in, check-out, presence score, and scans.

    Attributes:
        id: UUID primary key
        student_id: Foreign key to student user
        schedule_id: Foreign key to schedule
        date: Date of attendance
        status: Attendance status (present, late, absent, early_leave)
        check_in_time: First detection time
        check_out_time: Last detection time
        presence_score: Percentage of scans where student was detected
        total_scans: Total number of scans during session
        scans_present: Number of scans where student was detected
        remarks: Optional remarks/notes
    """

    __tablename__ = "attendance_records"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id"), nullable=False, index=True)

    # Date
    date = Column(Date, default=date.today, nullable=False, index=True)

    # Status
    status = Column(SQLEnum(AttendanceStatus), default=AttendanceStatus.ABSENT, nullable=False)

    # Times
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)

    # Presence metrics
    presence_score = Column(Float, default=0.0, nullable=False)  # 0-100
    total_scans = Column(Integer, default=0, nullable=False)
    scans_present = Column(Integer, default=0, nullable=False)

    # Notes
    remarks = Column(Text, nullable=True)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], backref="attendance_records")
    schedule = relationship("Schedule", backref="attendance_records")
    # presence_logs = relationship("PresenceLog", back_populates="attendance_record")
    # early_leave_events = relationship("EarlyLeaveEvent", back_populates="attendance_record")

    # Unique constraint (one record per student per schedule per date)
    __table_args__ = (
        UniqueConstraint('student_id', 'schedule_id', 'date', name='uq_student_schedule_date'),
    )

    def __repr__(self):
        return f"<AttendanceRecord(id={self.id}, student_id={self.student_id}, date={self.date}, status={self.status})>"
