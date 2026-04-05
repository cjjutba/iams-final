"""
Prediction Repository

Data access layer for AttendancePrediction operations.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.attendance_prediction import AttendancePrediction, RiskLevel


class PredictionRepository:
    """Repository for AttendancePrediction CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        student_id: str,
        schedule_id: str,
        week_start: date,
        predicted_rate: float,
        trend: str,
        risk_level: RiskLevel,
    ) -> AttendancePrediction:
        """Create a new prediction record."""
        prediction = AttendancePrediction(
            student_id=uuid.UUID(student_id),
            schedule_id=uuid.UUID(schedule_id),
            week_start=week_start,
            predicted_rate=predicted_rate,
            trend=trend,
            risk_level=risk_level,
        )
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    def get_by_schedule(self, schedule_id: str, week_start: date) -> list[AttendancePrediction]:
        """Get all predictions for a schedule for a given week."""
        return (
            self.db.query(AttendancePrediction)
            .filter(
                AttendancePrediction.schedule_id == uuid.UUID(schedule_id),
                AttendancePrediction.week_start == week_start,
            )
            .order_by(AttendancePrediction.predicted_rate.asc())
            .all()
        )

    def get_at_risk(self, min_risk: RiskLevel = RiskLevel.MODERATE) -> list[AttendancePrediction]:
        """Get all at-risk predictions (critical, high, moderate)."""
        risk_levels = [RiskLevel.CRITICAL, RiskLevel.HIGH]
        if min_risk == RiskLevel.MODERATE:
            risk_levels.append(RiskLevel.MODERATE)
        return (
            self.db.query(AttendancePrediction)
            .filter(AttendancePrediction.risk_level.in_(risk_levels))
            .order_by(AttendancePrediction.predicted_rate.asc())
            .all()
        )

    def update_actual_rate(self, prediction_id: str, actual_rate: float) -> AttendancePrediction | None:
        """Update a prediction with the actual rate after the week ends."""
        pred = self.db.query(AttendancePrediction).filter(AttendancePrediction.id == uuid.UUID(prediction_id)).first()
        if pred:
            pred.actual_rate = actual_rate
            self.db.commit()
            self.db.refresh(pred)
        return pred
