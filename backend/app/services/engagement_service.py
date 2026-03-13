"""
Engagement Service

Computes engagement scores from presence logs for each attendance session.

Scoring formula (configurable weights):
- Consistency (40%): StdDev of gaps between detected scans (lower variance = higher)
- Punctuality (20%): Time of first detection vs class start
- Sustained Presence (30%): Longest consecutive detection streak / total scans
- Confidence (10%): Mean recognition confidence across all presence logs
"""

from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from app.config import logger
from app.models.engagement_score import EngagementScore
from app.models.presence_log import PresenceLog
from app.repositories.engagement_repository import EngagementRepository

# Scoring weights (must sum to 1.0)
W_CONSISTENCY = 0.4
W_PUNCTUALITY = 0.2
W_SUSTAINED = 0.3
W_CONFIDENCE = 0.1


def compute_consistency_score(scan_times: list[datetime]) -> float:
    """Score based on regularity of detection gaps.

    Perfect consistency (equal gaps) = 100. High variance = lower score.

    Args:
        scan_times: Sorted timestamps of detected scans

    Returns:
        Score 0-100
    """
    if len(scan_times) < 2:
        return 0.0

    gaps = []
    for i in range(1, len(scan_times)):
        gap = (scan_times[i] - scan_times[i - 1]).total_seconds()
        gaps.append(gap)

    if not gaps:
        return 0.0

    mean_gap = np.mean(gaps)
    if mean_gap == 0:
        return 100.0

    std_gap = np.std(gaps)
    # Coefficient of variation (lower = more consistent)
    cv = std_gap / mean_gap if mean_gap > 0 else 0.0

    # Map CV to score: CV=0 → 100, CV>=2 → 0
    score = max(0.0, 100.0 * (1.0 - cv / 2.0))
    return float(score)


def compute_punctuality_score(
    first_detection: datetime | None,
    class_start: datetime,
    grace_minutes: int = 15,
) -> float:
    """Score based on arrival timeliness.

    On time or early = 100. Proportional decay through grace period.
    After grace period = 0.

    Args:
        first_detection: Time of first detection (None if never detected)
        class_start: Scheduled class start time
        grace_minutes: Grace period in minutes

    Returns:
        Score 0-100
    """
    if first_detection is None:
        return 0.0

    diff_seconds = (first_detection - class_start).total_seconds()

    if diff_seconds <= 0:
        # On time or early
        return 100.0

    grace_seconds = grace_minutes * 60
    if diff_seconds >= grace_seconds:
        return 0.0

    # Linear decay through grace period
    return float(100.0 * (1.0 - diff_seconds / grace_seconds))


def compute_sustained_presence_score(
    detected_flags: list[bool],
) -> float:
    """Score based on longest consecutive detection streak.

    Ratio of longest streak to total scans × 100.

    Args:
        detected_flags: Ordered list of detection booleans

    Returns:
        Score 0-100
    """
    if not detected_flags:
        return 0.0

    total = len(detected_flags)
    max_streak = 0
    current_streak = 0

    for detected in detected_flags:
        if detected:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return float(100.0 * max_streak / total)


def compute_confidence_score(confidences: list[float]) -> float:
    """Score based on average recognition confidence.

    Maps mean confidence to 0-100 scale.

    Args:
        confidences: List of recognition confidence values (0-1)

    Returns:
        Score 0-100
    """
    if not confidences:
        return 0.0

    mean_conf = float(np.mean(confidences))
    # Confidence is already 0-1, scale to 0-100
    return min(100.0, mean_conf * 100.0)


class EngagementService:
    """Service for computing and managing engagement scores."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = EngagementRepository(db)

    def compute_session_engagement(
        self,
        attendance_id: str,
        class_start: datetime,
        grace_minutes: int = 15,
    ) -> EngagementScore:
        """Compute engagement score for a completed attendance session.

        Fetches presence logs, computes component scores, and stores result.

        Args:
            attendance_id: Attendance record ID
            class_start: Scheduled class start time
            grace_minutes: Grace period for punctuality

        Returns:
            EngagementScore record
        """
        import uuid as _uuid

        # Fetch presence logs for this attendance record
        logs = (
            self.db.query(PresenceLog)
            .filter(PresenceLog.attendance_id == _uuid.UUID(attendance_id))
            .order_by(PresenceLog.scan_number)
            .all()
        )

        if not logs:
            logger.debug(f"No presence logs for attendance {attendance_id}")
            return self.repo.upsert(
                attendance_id,
                consistency_score=0.0,
                punctuality_score=0.0,
                sustained_presence_score=0.0,
                confidence_avg=None,
                engagement_score=0.0,
            )

        # Extract data from logs
        detected_times = [log.scan_time for log in logs if log.detected]
        detected_flags = [log.detected for log in logs]
        confidences = [log.confidence for log in logs if log.detected and log.confidence is not None]
        first_detection = detected_times[0] if detected_times else None

        # Compute component scores
        consistency = compute_consistency_score(detected_times)
        punctuality = compute_punctuality_score(first_detection, class_start, grace_minutes)
        sustained = compute_sustained_presence_score(detected_flags)
        confidence = compute_confidence_score(confidences)
        conf_avg = float(np.mean(confidences)) if confidences else None

        # Weighted composite
        composite = (
            W_CONSISTENCY * consistency
            + W_PUNCTUALITY * punctuality
            + W_SUSTAINED * sustained
            + W_CONFIDENCE * confidence
        )

        logger.info(
            f"Engagement for attendance {attendance_id}: "
            f"consistency={consistency:.1f}, punctuality={punctuality:.1f}, "
            f"sustained={sustained:.1f}, confidence={confidence:.1f}, "
            f"composite={composite:.1f}"
        )

        return self.repo.upsert(
            attendance_id,
            consistency_score=consistency,
            punctuality_score=punctuality,
            sustained_presence_score=sustained,
            confidence_avg=conf_avg,
            engagement_score=composite,
        )
