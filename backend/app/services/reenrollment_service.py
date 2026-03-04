"""
Re-enrollment Monitoring Service

Tracks rolling window of per-user recognition similarity scores.
When a user's mean similarity drops below a threshold, triggers
a re-registration notification.
"""

from collections import defaultdict, deque
from typing import Dict, Optional

from app.config import settings, logger


class ReenrollmentMonitor:
    """
    In-memory tracker of per-user recognition similarity scores.

    Thread-safe for single-writer (recognition loop) usage.
    Stores a rolling window of the last N similarity scores per user.
    """

    def __init__(
        self,
        threshold: float = None,
        window_size: int = None,
    ):
        self.threshold = threshold or settings.REENROLL_SIMILARITY_THRESHOLD
        self.window_size = window_size or settings.REENROLL_WINDOW_SIZE
        self._scores: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        # Track which users have been notified to avoid spam
        self._notified: set = set()

    def record_similarity(self, user_id: str, similarity: float) -> Optional[str]:
        """
        Record a similarity score for a recognized user.

        Returns user_id if re-enrollment should be prompted (mean dropped
        below threshold and user hasn't been notified yet), else None.
        """
        window = self._scores[user_id]
        window.append(similarity)

        # Need a full window before checking
        if len(window) < self.window_size:
            return None

        mean_sim = sum(window) / len(window)

        if mean_sim < self.threshold and user_id not in self._notified:
            self._notified.add(user_id)
            logger.info(
                f"Re-enrollment prompt for user {user_id}: "
                f"mean similarity {mean_sim:.3f} < {self.threshold}"
            )
            return user_id

        # If similarity recovers (e.g. after re-registration), reset notification
        if mean_sim >= self.threshold and user_id in self._notified:
            self._notified.discard(user_id)

        return None

    def get_mean_similarity(self, user_id: str) -> Optional[float]:
        """Get current mean similarity for a user, or None if insufficient data."""
        window = self._scores.get(user_id)
        if not window or len(window) < self.window_size:
            return None
        return sum(window) / len(window)

    def reset_user(self, user_id: str) -> None:
        """Clear tracking data for a user (e.g. after re-registration)."""
        self._scores.pop(user_id, None)
        self._notified.discard(user_id)

    def clear(self) -> None:
        """Clear all tracking data."""
        self._scores.clear()
        self._notified.clear()


# Global singleton
reenrollment_monitor = ReenrollmentMonitor()
