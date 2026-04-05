"""
Adaptive Threshold Manager

Tracks face recognition match statistics per room and recommends
similarity thresholds that adapt to environmental conditions (lighting,
camera angle, distance).

Algorithm:
- Maintains rolling window of positive/negative match similarities per room
- Computes midpoint between mean positive and mean negative distributions
- Clamps to [floor, ceiling] range
- Requires minimum sample count before adapting (falls back to global default)
"""

from collections import deque
from dataclasses import dataclass, field

from app.config import logger, settings


@dataclass
class _RoomAccumulator:
    """Tracks match/non-match similarity distributions for a single room."""

    positive: deque = field(default_factory=lambda: deque(maxlen=settings.ADAPTIVE_THRESHOLD_WINDOW))
    negative: deque = field(default_factory=lambda: deque(maxlen=settings.ADAPTIVE_THRESHOLD_WINDOW))


class AdaptiveThresholdManager:
    """Tracks match statistics per room and recommends thresholds."""

    def __init__(self):
        self._room_stats: dict[str, _RoomAccumulator] = {}

    def _get_room(self, room_id: str) -> _RoomAccumulator:
        if room_id not in self._room_stats:
            self._room_stats[room_id] = _RoomAccumulator()
        return self._room_stats[room_id]

    def record_match(self, room_id: str, similarity: float, is_match: bool) -> None:
        """Record a recognition result for threshold adaptation.

        Args:
            room_id: Room identifier
            similarity: Cosine similarity score from FAISS
            is_match: True if this was a confirmed match (above current threshold)
        """
        room = self._get_room(room_id)
        if is_match:
            room.positive.append(similarity)
        else:
            room.negative.append(similarity)

    def get_threshold(self, room_id: str) -> float:
        """Get the recommended threshold for a room.

        Returns the adaptive threshold if enough samples exist, otherwise
        falls back to the global RECOGNITION_THRESHOLD.

        Args:
            room_id: Room identifier

        Returns:
            Recommended similarity threshold
        """
        if not settings.ADAPTIVE_THRESHOLD_ENABLED:
            return settings.RECOGNITION_THRESHOLD

        room = self._room_stats.get(room_id)
        if room is None:
            return settings.RECOGNITION_THRESHOLD

        total = len(room.positive) + len(room.negative)
        if total < settings.ADAPTIVE_THRESHOLD_MIN_SAMPLES:
            return settings.RECOGNITION_THRESHOLD

        # Need both positive and negative samples for midpoint
        if not room.positive or not room.negative:
            return settings.RECOGNITION_THRESHOLD

        mean_pos = sum(room.positive) / len(room.positive)
        mean_neg = sum(room.negative) / len(room.negative)

        # Midpoint between distributions
        midpoint = (mean_pos + mean_neg) / 2.0

        # Clamp to floor/ceiling
        threshold = max(
            settings.ADAPTIVE_THRESHOLD_FLOOR,
            min(settings.ADAPTIVE_THRESHOLD_CEILING, midpoint),
        )

        logger.debug(
            f"Adaptive threshold for room {room_id}: {threshold:.3f} "
            f"(pos_mean={mean_pos:.3f}, neg_mean={mean_neg:.3f}, "
            f"samples={total})"
        )

        return threshold

    def get_stats(self, room_id: str) -> dict:
        """Get statistics for a room's threshold adaptation."""
        room = self._room_stats.get(room_id)
        if room is None:
            return {
                "room_id": room_id,
                "positive_count": 0,
                "negative_count": 0,
                "current_threshold": settings.RECOGNITION_THRESHOLD,
                "adapted": False,
            }

        total = len(room.positive) + len(room.negative)
        adapted = total >= settings.ADAPTIVE_THRESHOLD_MIN_SAMPLES
        return {
            "room_id": room_id,
            "positive_count": len(room.positive),
            "negative_count": len(room.negative),
            "positive_mean": sum(room.positive) / len(room.positive) if room.positive else None,
            "negative_mean": sum(room.negative) / len(room.negative) if room.negative else None,
            "current_threshold": self.get_threshold(room_id),
            "adapted": adapted,
        }

    def reset(self, room_id: str | None = None) -> None:
        """Reset statistics for a room or all rooms."""
        if room_id:
            self._room_stats.pop(room_id, None)
        else:
            self._room_stats.clear()


# Global instance
threshold_manager = AdaptiveThresholdManager()
