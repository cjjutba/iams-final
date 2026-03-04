"""
Predictive Attendance Service

Uses exponentially weighted moving average (EWMA) and linear regression
to predict upcoming attendance rates and classify risk levels.

No ML dependencies required — uses only numpy (already installed).
"""

from datetime import date, timedelta
from typing import List, Optional, Tuple

import numpy as np

from app.config import logger
from app.models.attendance_prediction import RiskLevel


# ---------------------------------------------------------------------------
# Pure prediction functions (stateless, testable)
# ---------------------------------------------------------------------------

def compute_ewma(rates: List[float], alpha: float = 0.3) -> float:
    """
    Compute exponentially weighted moving average.

    Args:
        rates: Historical weekly rates (oldest first)
        alpha: Smoothing factor (0 < alpha <= 1). Higher = more weight on recent.

    Returns:
        Predicted rate for next period.
    """
    if not rates:
        return 0.0
    if len(rates) == 1:
        return rates[0]

    ewma = rates[0]
    for rate in rates[1:]:
        ewma = alpha * rate + (1 - alpha) * ewma
    return float(ewma)


def compute_trend(rates: List[float], min_points: int = 3) -> Tuple[str, float]:
    """
    Compute trend direction via simple linear regression on weekly rates.

    Args:
        rates: Historical weekly rates (oldest first)
        min_points: Minimum data points for regression

    Returns:
        Tuple of (trend_label, slope)
        - trend_label: 'improving', 'stable', or 'declining'
        - slope: Change in rate per week
    """
    if len(rates) < min_points:
        return "stable", 0.0

    x = np.arange(len(rates), dtype=np.float64)
    y = np.array(rates, dtype=np.float64)

    # Simple linear regression: y = mx + b
    n = len(x)
    sum_x = np.sum(x)
    sum_y = np.sum(y)
    sum_xy = np.sum(x * y)
    sum_x2 = np.sum(x * x)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-10:
        return "stable", 0.0

    slope = float((n * sum_xy - sum_x * sum_y) / denom)

    # Classify trend based on slope magnitude
    if slope > 2.0:
        return "improving", slope
    elif slope < -2.0:
        return "declining", slope
    return "stable", slope


def classify_risk(predicted_rate: float) -> RiskLevel:
    """
    Classify risk level based on predicted attendance rate.

    Args:
        predicted_rate: Predicted rate (0-100)

    Returns:
        RiskLevel enum
    """
    if predicted_rate < 50.0:
        return RiskLevel.CRITICAL
    elif predicted_rate < 65.0:
        return RiskLevel.HIGH
    elif predicted_rate < 80.0:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def predict_next_week(
    weekly_rates: List[float], alpha: float = 0.3
) -> dict:
    """
    Generate a prediction for the next week.

    Args:
        weekly_rates: Historical weekly rates (oldest first)
        alpha: EWMA smoothing factor

    Returns:
        dict with predicted_rate, trend, risk_level
    """
    predicted = compute_ewma(weekly_rates, alpha=alpha)
    predicted = max(0.0, min(100.0, predicted))  # Clamp to [0, 100]

    trend_label, slope = compute_trend(weekly_rates)
    risk = classify_risk(predicted)

    return {
        "predicted_rate": round(predicted, 1),
        "trend": trend_label,
        "slope": round(slope, 2),
        "risk_level": risk,
    }


# ---------------------------------------------------------------------------
# Orchestrator (DB-aware)
# ---------------------------------------------------------------------------

class PredictionService:
    """Orchestrates weekly prediction generation."""

    def __init__(self, db):
        from sqlalchemy.orm import Session
        from app.models.attendance_record import AttendanceRecord, AttendanceStatus
        from app.models.enrollment import Enrollment
        from app.models.schedule import Schedule
        from app.repositories.prediction_repository import PredictionRepository

        self.db: Session = db
        self.repo = PredictionRepository(db)
        self._AttendanceRecord = AttendanceRecord
        self._AttendanceStatus = AttendanceStatus
        self._Enrollment = Enrollment
        self._Schedule = Schedule

    def run_weekly_predictions(self, target_week_start: Optional[date] = None):
        """
        Generate predictions for all active enrollments.

        Args:
            target_week_start: Start of the week to predict (default: next Monday)
        """
        if target_week_start is None:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            target_week_start = today + timedelta(days=days_until_monday)

        # Get all active schedules
        schedules = self.db.query(self._Schedule).all()
        created = 0

        for schedule in schedules:
            # Get enrolled students
            enrollments = (
                self.db.query(self._Enrollment)
                .filter(self._Enrollment.schedule_id == schedule.id)
                .all()
            )

            for enrollment in enrollments:
                student_id = str(enrollment.student_id)
                schedule_id = str(schedule.id)

                # Get weekly rates for last 8 weeks
                weekly_rates = self._get_weekly_rates(
                    student_id, schedule_id, weeks=8
                )

                if len(weekly_rates) < 2:
                    continue  # Not enough history

                prediction = predict_next_week(weekly_rates)

                self.repo.create(
                    student_id=student_id,
                    schedule_id=schedule_id,
                    week_start=target_week_start,
                    predicted_rate=prediction["predicted_rate"],
                    trend=prediction["trend"],
                    risk_level=prediction["risk_level"],
                )
                created += 1

        logger.info(f"Generated {created} attendance predictions for week {target_week_start}")
        return created

    def _get_weekly_rates(
        self, student_id: str, schedule_id: str, weeks: int = 8
    ) -> List[float]:
        """Get weekly attendance rates for a student in a schedule."""
        import uuid
        today = date.today()
        rates = []

        for w in range(weeks, 0, -1):
            week_start = today - timedelta(weeks=w)
            week_end = week_start + timedelta(days=7)

            records = (
                self.db.query(self._AttendanceRecord)
                .filter(
                    self._AttendanceRecord.student_id == uuid.UUID(student_id),
                    self._AttendanceRecord.schedule_id == uuid.UUID(schedule_id),
                    self._AttendanceRecord.date >= week_start,
                    self._AttendanceRecord.date < week_end,
                )
                .all()
            )

            if records:
                present = sum(
                    1 for r in records
                    if r.status in (
                        self._AttendanceStatus.PRESENT,
                        self._AttendanceStatus.LATE,
                    )
                )
                rates.append((present / len(records)) * 100.0)

        return rates
