"""
Anomaly Detection Service

Detects unusual attendance patterns:
- Sudden absence: strong-history student suddenly absent
- Proxy suspect: same face in 2 rooms simultaneously
- Pattern break: significant deviation from personal mean
- Low confidence: consistently low recognition confidence
"""

import json
from datetime import date, timedelta

import numpy as np
from sqlalchemy.orm import Session

from app.config import logger
from app.models.attendance_anomaly import AnomalyType, AttendanceAnomaly
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.presence_log import PresenceLog
from app.models.schedule import Schedule
from app.repositories.anomaly_repository import AnomalyRepository

# ---------------------------------------------------------------------------
# Pure detector functions (stateless, easily testable)
# ---------------------------------------------------------------------------


def detect_sudden_absence(
    historical_rate: float,
    is_absent_today: bool,
    min_history_rate: float = 80.0,
) -> dict | None:
    """
    Detect when a student with strong attendance history is suddenly absent.

    Args:
        historical_rate: Attendance rate over recent history (0-100)
        is_absent_today: Whether student is absent today
        min_history_rate: Minimum historical rate to trigger (default 80%)

    Returns:
        Dict with anomaly details if detected, None otherwise
    """
    if not is_absent_today:
        return None
    if historical_rate < min_history_rate:
        return None

    severity = "high" if historical_rate >= 95.0 else "medium"
    return {
        "anomaly_type": AnomalyType.SUDDEN_ABSENCE,
        "severity": severity,
        "confidence": min(historical_rate / 100.0, 1.0),
        "description": (f"Student with {historical_rate:.0f}% attendance rate is unexpectedly absent"),
        "details": {
            "historical_rate": historical_rate,
        },
    }


def detect_proxy_suspect(
    concurrent_sessions: list[tuple[str, str]],
) -> dict | None:
    """
    Detect when the same user appears in multiple active sessions simultaneously.

    Args:
        concurrent_sessions: List of (schedule_id, room_name) tuples where
                           the student was detected in overlapping time windows.

    Returns:
        Dict with anomaly details if detected, None otherwise.
    """
    if len(concurrent_sessions) < 2:
        return None

    rooms = [room for _, room in concurrent_sessions]
    return {
        "anomaly_type": AnomalyType.PROXY_SUSPECT,
        "severity": "high",
        "confidence": 0.9,
        "description": (f"Student detected in {len(concurrent_sessions)} rooms simultaneously: {', '.join(rooms)}"),
        "details": {
            "sessions": [{"schedule_id": sid, "room": room} for sid, room in concurrent_sessions],
        },
    }


def detect_pattern_break(
    weekly_rates: list[float],
    current_week_rate: float,
    std_dev_threshold: float = 2.0,
    min_weeks: int = 3,
) -> dict | None:
    """
    Detect when current week significantly deviates from personal history.

    Args:
        weekly_rates: Historical weekly attendance rates (last N weeks)
        current_week_rate: This week's rate
        std_dev_threshold: Number of std devs to trigger
        min_weeks: Minimum weeks of history required

    Returns:
        Dict with anomaly details if detected, None otherwise
    """
    if len(weekly_rates) < min_weeks:
        return None

    mean = float(np.mean(weekly_rates))
    std = float(np.std(weekly_rates))

    if std < 1.0:
        # Very consistent student — any significant drop is notable
        std = 5.0  # Use a small fixed value

    deviation = (mean - current_week_rate) / std

    if deviation < std_dev_threshold:
        return None

    severity = "high" if deviation >= 3.0 else "medium"
    return {
        "anomaly_type": AnomalyType.PATTERN_BREAK,
        "severity": severity,
        "confidence": min(deviation / 4.0, 1.0),
        "description": (
            f"Attendance dropped to {current_week_rate:.0f}% "
            f"(personal average: {mean:.0f}%, {deviation:.1f} std devs below)"
        ),
        "details": {
            "mean": mean,
            "std_dev": std,
            "deviation": deviation,
            "current_rate": current_week_rate,
            "weekly_rates": weekly_rates,
        },
    }


def detect_low_confidence(
    avg_confidence: float,
    threshold: float = 0.5,
    scan_count: int = 0,
    min_scans: int = 3,
) -> dict | None:
    """
    Detect consistently low recognition confidence across a session.

    Args:
        avg_confidence: Mean recognition confidence for the session
        threshold: Maximum avg confidence to trigger
        scan_count: Number of scans in the session
        min_scans: Minimum scans required to trigger

    Returns:
        Dict with anomaly details if detected, None otherwise
    """
    if scan_count < min_scans:
        return None
    if avg_confidence >= threshold:
        return None

    severity = "high" if avg_confidence < 0.3 else "medium" if avg_confidence < 0.4 else "low"
    return {
        "anomaly_type": AnomalyType.LOW_CONFIDENCE,
        "severity": severity,
        "confidence": 1.0 - avg_confidence,  # Higher anomaly confidence when recognition is worse
        "description": (
            f"Average recognition confidence of {avg_confidence:.2f} "
            f"across {scan_count} scans (threshold: {threshold:.2f})"
        ),
        "details": {
            "avg_confidence": avg_confidence,
            "scan_count": scan_count,
        },
    }


# ---------------------------------------------------------------------------
# Orchestrator service (DB-aware)
# ---------------------------------------------------------------------------


class AnomalyService:
    """Orchestrates anomaly detection using DB data."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = AnomalyRepository(db)

    def run_post_session_checks(
        self,
        student_id: str,
        schedule_id: str,
        attendance_record: AttendanceRecord,
    ) -> list[AttendanceAnomaly]:
        """
        Run all anomaly detectors after a session ends.

        Returns list of created anomaly records.
        """
        created = []

        # 1. Sudden absence check
        anomaly = self._check_sudden_absence(student_id, schedule_id, attendance_record)
        if anomaly:
            created.append(anomaly)

        # 2. Low confidence check
        anomaly = self._check_low_confidence(student_id, attendance_record)
        if anomaly:
            created.append(anomaly)

        # 3. Pattern break check (weekly)
        anomaly = self._check_pattern_break(student_id)
        if anomaly:
            created.append(anomaly)

        return created

    def check_proxy(self, student_id: str, current_schedule_id: str) -> AttendanceAnomaly | None:
        """
        Check if student is detected in multiple active sessions.
        Called during live scanning, not post-session.
        """
        try:
            today = date.today()
            # Find all attendance records for this student today with present status
            records = (
                self.db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.date == today,
                    AttendanceRecord.status.in_(
                        [
                            AttendanceStatus.PRESENT,
                            AttendanceStatus.LATE,
                        ]
                    ),
                )
                .all()
            )

            if len(records) < 2:
                return None

            # Check for overlapping schedules
            concurrent = []
            for rec in records:
                schedule = self.db.query(Schedule).filter(Schedule.id == rec.schedule_id).first()
                if schedule:
                    concurrent.append(
                        (
                            str(rec.schedule_id),
                            schedule.room_name if hasattr(schedule, "room_name") else str(schedule.room_id),
                        )
                    )

            result = detect_proxy_suspect(concurrent)
            if result:
                return self.repo.create(
                    student_id=student_id,
                    schedule_id=current_schedule_id,
                    anomaly_type=result["anomaly_type"],
                    severity=result["severity"],
                    description=result["description"],
                    details=json.dumps(result["details"]),
                    confidence=result["confidence"],
                )
        except Exception as e:
            logger.error(f"Proxy check failed for student {student_id}: {e}")
        return None

    def _check_sudden_absence(
        self,
        student_id: str,
        schedule_id: str,
        attendance: AttendanceRecord,
    ) -> AttendanceAnomaly | None:
        """Check for sudden absence anomaly."""
        try:
            is_absent = attendance.status == AttendanceStatus.ABSENT

            if not is_absent:
                return None

            # Calculate historical attendance rate (last 4 weeks)
            four_weeks_ago = date.today() - timedelta(weeks=4)
            history = (
                self.db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.schedule_id == schedule_id,
                    AttendanceRecord.date >= four_weeks_ago,
                    AttendanceRecord.date < date.today(),
                )
                .all()
            )

            if len(history) < 3:
                return None

            present_count = sum(1 for r in history if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
            rate = (present_count / len(history)) * 100.0

            result = detect_sudden_absence(rate, is_absent)
            if result:
                return self.repo.create(
                    student_id=student_id,
                    schedule_id=schedule_id,
                    anomaly_type=result["anomaly_type"],
                    severity=result["severity"],
                    description=result["description"],
                    details=json.dumps(result["details"]),
                    confidence=result["confidence"],
                )
        except Exception as e:
            logger.error(f"Sudden absence check failed: {e}")
        return None

    def _check_low_confidence(self, student_id: str, attendance: AttendanceRecord) -> AttendanceAnomaly | None:
        """Check for low recognition confidence anomaly."""
        try:
            # Get presence logs for this attendance
            logs = (
                self.db.query(PresenceLog)
                .filter(
                    PresenceLog.attendance_id == attendance.id,
                    PresenceLog.detected == True,  # noqa: E712
                )
                .all()
            )

            if not logs:
                return None

            confidences = [log.confidence for log in logs if log.confidence is not None]

            if not confidences:
                return None

            avg_conf = float(np.mean(confidences))
            result = detect_low_confidence(avg_conf, scan_count=len(confidences))

            if result:
                return self.repo.create(
                    student_id=student_id,
                    schedule_id=str(attendance.schedule_id),
                    anomaly_type=result["anomaly_type"],
                    severity=result["severity"],
                    description=result["description"],
                    details=json.dumps(result["details"]),
                    confidence=result["confidence"],
                )
        except Exception as e:
            logger.error(f"Low confidence check failed: {e}")
        return None

    def _check_pattern_break(self, student_id: str) -> AttendanceAnomaly | None:
        """Check for weekly pattern break anomaly."""
        try:
            today = date.today()
            # Get weekly rates for last 5 weeks
            weekly_rates = []
            for weeks_ago in range(5, 0, -1):
                week_start = today - timedelta(weeks=weeks_ago)
                week_end = week_start + timedelta(days=7)
                records = (
                    self.db.query(AttendanceRecord)
                    .filter(
                        AttendanceRecord.student_id == student_id,
                        AttendanceRecord.date >= week_start,
                        AttendanceRecord.date < week_end,
                    )
                    .all()
                )
                if records:
                    present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
                    weekly_rates.append((present / len(records)) * 100.0)

            # Current week
            current_week_start = today - timedelta(days=today.weekday())
            current_records = (
                self.db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.date >= current_week_start,
                    AttendanceRecord.date <= today,
                )
                .all()
            )

            if not current_records:
                return None

            current_present = sum(
                1 for r in current_records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
            )
            current_rate = (current_present / len(current_records)) * 100.0

            result = detect_pattern_break(weekly_rates, current_rate)
            if result:
                return self.repo.create(
                    student_id=student_id,
                    anomaly_type=result["anomaly_type"],
                    severity=result["severity"],
                    description=result["description"],
                    details=json.dumps(result["details"]),
                    confidence=result["confidence"],
                )
        except Exception as e:
            logger.error(f"Pattern break check failed: {e}")
        return None
