"""
Attendance Anomaly Model

Records detected anomalies in attendance patterns.
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

    SUDDEN_ABSENCE = "sudden_absence"  # Strong-history student suddenly absent
    PROXY_SUSPECT = "proxy_suspect"  # Same face in 2 rooms simultaneously
    PATTERN_BREAK = "pattern_break"  # Significant deviation from personal mean
    LOW_CONFIDENCE = "low_confidence"  # Consistently low recognition confidence


class AttendanceAnomaly(Base):
    """
    Attendance anomaly model

    Records when the system detects unusual attendance patterns.

    Attributes:
        id: UUID primary key
        student_id: Foreign key to user
        schedule_id: Optional foreign key to schedule
        anomaly_type: Type of anomaly detected
        severity: 'low', 'medium', 'high'
        description: Human-readable description
        details: JSON-serializable details string
        confidence: Detection confidence (0.0-1.0)
        resolved: Whether anomaly has been reviewed/resolved
        resolved_by: Faculty/admin who resolved it
        resolved_at: When it was resolved
        detected_at: When anomaly was detected
    """

    __tablename__ = "attendance_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id"), nullable=True, index=True)
    anomaly_type = Column(SQLEnum(AnomalyType), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="medium")
    description = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], backref="anomalies")
    schedule = relationship("Schedule", backref="anomalies")

    def __repr__(self):
        return f"<AttendanceAnomaly(id={self.id}, type={self.anomaly_type}, student={self.student_id})>"
