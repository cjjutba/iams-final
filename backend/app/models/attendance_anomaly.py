"""
Attendance Anomaly Model

Records anomalous attendance patterns detected by the analytics engine.
Examples: sudden drops in attendance, impossible check-in patterns, etc.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AnomalyType(enum.StrEnum):
    """Types of attendance anomalies."""

    SUDDEN_DROP = "sudden_drop"
    IMPOSSIBLE_CHECKIN = "impossible_checkin"
    PATTERN_BREAK = "pattern_break"
    PROXY_SUSPECTED = "proxy_suspected"
    EARLY_LEAVE_PATTERN = "early_leave_pattern"
    LOW_ENGAGEMENT = "low_engagement"


class AttendanceAnomaly(Base):
    """
    Attendance anomaly model

    Records anomalous attendance patterns detected by the system.

    Attributes:
        id: UUID primary key
        student_id: Foreign key to student user
        schedule_id: Foreign key to schedule (optional, anomaly may be cross-schedule)
        anomaly_type: Type of anomaly detected
        severity: Severity level (low, medium, high, critical)
        description: Human-readable description of the anomaly
        details: Additional details (JSON-encoded or free text)
        confidence: Confidence score of the anomaly detection (0-1)
        detected_at: When the anomaly was detected
        resolved: Whether the anomaly has been resolved/reviewed
        resolved_by: Foreign key to admin/faculty who resolved it
        resolved_at: When the anomaly was resolved
    """

    __tablename__ = "attendance_anomalies"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True, index=True)

    # Anomaly details
    anomaly_type = Column(SQLEnum(AnomalyType), nullable=False, index=True)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    # Timestamps
    detected_at = Column(DateTime, default=lambda: datetime.now(), nullable=False, index=True)

    # Resolution
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    schedule = relationship("Schedule", foreign_keys=[schedule_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return (
            f"<AttendanceAnomaly(id={self.id}, type={self.anomaly_type}, "
            f"severity={self.severity}, resolved={self.resolved})>"
        )
