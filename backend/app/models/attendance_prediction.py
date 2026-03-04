"""
Attendance Prediction Model

Stores weekly predicted attendance rates and risk classifications.
"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, Float, Date, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RiskLevel(str, enum.Enum):
    """Risk classification for attendance predictions."""
    CRITICAL = "critical"    # <50% predicted rate
    HIGH = "high"            # 50-65%
    MODERATE = "moderate"    # 65-80%
    LOW = "low"              # >80%


class AttendancePrediction(Base):
    """
    Attendance prediction model

    Stores per-student, per-schedule weekly predictions.

    Attributes:
        id: UUID primary key
        student_id: FK to users
        schedule_id: FK to schedules
        week_start: Start of the predicted week
        predicted_rate: EWMA-predicted attendance rate (0-100)
        trend: Trend direction ('improving', 'stable', 'declining')
        risk_level: Risk classification
        actual_rate: Filled in after the week ends
        computed_at: When the prediction was generated
    """

    __tablename__ = "attendance_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id"), nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    predicted_rate = Column(Float, nullable=False)
    trend = Column(String(20), nullable=False, default="stable")
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    actual_rate = Column(Float, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], backref="predictions")
    schedule = relationship("Schedule", backref="predictions")

    def __repr__(self):
        return (
            f"<AttendancePrediction(student={self.student_id}, "
            f"week={self.week_start}, predicted={self.predicted_rate:.0f}%, "
            f"risk={self.risk_level})>"
        )
