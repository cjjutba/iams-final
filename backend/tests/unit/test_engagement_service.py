"""
Unit Tests for Engagement Service

Tests component scoring functions and composite engagement computation.
"""

from datetime import datetime, timedelta

import pytest

from app.services.engagement_service import (
    compute_consistency_score,
    compute_punctuality_score,
    compute_sustained_presence_score,
    compute_confidence_score,
)


# ---------------------------------------------------------------------------
# Consistency Score
# ---------------------------------------------------------------------------

class TestConsistencyScore:
    def test_perfect_consistency(self):
        """Equally spaced detections → high score."""
        base = datetime(2026, 3, 4, 8, 0, 0)
        times = [base + timedelta(seconds=60 * i) for i in range(10)]
        score = compute_consistency_score(times)
        assert score > 95.0

    def test_irregular_gaps(self):
        """Highly irregular gaps → lower score."""
        base = datetime(2026, 3, 4, 8, 0, 0)
        # Gaps: 10s, 300s, 5s, 600s, 20s
        offsets = [0, 10, 310, 315, 915, 935]
        times = [base + timedelta(seconds=o) for o in offsets]
        score = compute_consistency_score(times)
        assert score < 50.0

    def test_single_detection(self):
        """Single detection → 0 (can't compute gaps)."""
        assert compute_consistency_score([datetime.now()]) == 0.0

    def test_empty(self):
        assert compute_consistency_score([]) == 0.0

    def test_two_detections(self):
        """Two detections → perfect consistency (one gap, zero variance)."""
        base = datetime(2026, 3, 4, 8, 0, 0)
        times = [base, base + timedelta(seconds=60)]
        score = compute_consistency_score(times)
        assert score == 100.0


# ---------------------------------------------------------------------------
# Punctuality Score
# ---------------------------------------------------------------------------

class TestPunctualityScore:
    def test_on_time(self):
        """Arriving at class start → 100."""
        start = datetime(2026, 3, 4, 8, 0, 0)
        assert compute_punctuality_score(start, start) == 100.0

    def test_early(self):
        """Arriving before class start → 100."""
        start = datetime(2026, 3, 4, 8, 0, 0)
        early = start - timedelta(minutes=5)
        assert compute_punctuality_score(early, start) == 100.0

    def test_half_grace(self):
        """Arriving halfway through grace period → ~50."""
        start = datetime(2026, 3, 4, 8, 0, 0)
        late = start + timedelta(minutes=7, seconds=30)
        score = compute_punctuality_score(late, start, grace_minutes=15)
        assert abs(score - 50.0) < 1.0

    def test_after_grace(self):
        """Arriving after grace period → 0."""
        start = datetime(2026, 3, 4, 8, 0, 0)
        very_late = start + timedelta(minutes=20)
        assert compute_punctuality_score(very_late, start, grace_minutes=15) == 0.0

    def test_never_detected(self):
        """Never detected → 0."""
        start = datetime(2026, 3, 4, 8, 0, 0)
        assert compute_punctuality_score(None, start) == 0.0


# ---------------------------------------------------------------------------
# Sustained Presence Score
# ---------------------------------------------------------------------------

class TestSustainedPresenceScore:
    def test_all_present(self):
        """All scans detected → 100."""
        flags = [True] * 10
        assert compute_sustained_presence_score(flags) == 100.0

    def test_all_absent(self):
        """No scans detected → 0."""
        flags = [False] * 10
        assert compute_sustained_presence_score(flags) == 0.0

    def test_partial_streak(self):
        """Longest streak of 5 out of 10 → 50."""
        flags = [True, True, True, True, True, False, True, True, False, False]
        score = compute_sustained_presence_score(flags)
        assert abs(score - 50.0) < 0.1

    def test_split_streaks(self):
        """Two equal streaks → uses the max."""
        flags = [True, True, True, False, True, True, True]
        score = compute_sustained_presence_score(flags)
        # Max streak = 3 out of 7 = 42.9
        assert abs(score - 100.0 * 3 / 7) < 0.1

    def test_empty(self):
        assert compute_sustained_presence_score([]) == 0.0


# ---------------------------------------------------------------------------
# Confidence Score
# ---------------------------------------------------------------------------

class TestConfidenceScore:
    def test_high_confidence(self):
        """High confidence values → high score."""
        confs = [0.9, 0.85, 0.95, 0.88]
        score = compute_confidence_score(confs)
        assert score > 85.0

    def test_low_confidence(self):
        """Low confidence values → low score."""
        confs = [0.3, 0.25, 0.35]
        score = compute_confidence_score(confs)
        assert score < 40.0

    def test_empty(self):
        assert compute_confidence_score([]) == 0.0

    def test_perfect_confidence(self):
        """All 1.0 → 100."""
        assert compute_confidence_score([1.0, 1.0, 1.0]) == 100.0
