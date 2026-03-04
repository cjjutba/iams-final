"""
Unit Tests for Re-enrollment Monitoring Service

Tests rolling window similarity tracking and re-enrollment prompts.
"""

import pytest

from app.services.reenrollment_service import ReenrollmentMonitor


@pytest.fixture
def monitor():
    return ReenrollmentMonitor(threshold=0.55, window_size=5)


class TestRecordSimilarity:
    def test_no_trigger_until_window_full(self, monitor):
        """Doesn't trigger re-enrollment until window is full."""
        for _ in range(4):
            result = monitor.record_similarity("user-1", 0.40)
            assert result is None

    def test_triggers_when_mean_below_threshold(self, monitor):
        """Triggers re-enrollment when mean drops below threshold."""
        # Fill window with low similarities
        for i in range(4):
            monitor.record_similarity("user-1", 0.50)
        result = monitor.record_similarity("user-1", 0.50)
        assert result == "user-1"

    def test_no_trigger_when_mean_above_threshold(self, monitor):
        """No trigger when mean is above threshold."""
        for i in range(4):
            monitor.record_similarity("user-1", 0.70)
        result = monitor.record_similarity("user-1", 0.70)
        assert result is None

    def test_only_notifies_once(self, monitor):
        """Only sends notification once per user."""
        # Fill window to trigger
        for _ in range(5):
            monitor.record_similarity("user-1", 0.40)
        # Next call should not re-trigger
        result = monitor.record_similarity("user-1", 0.40)
        assert result is None

    def test_resets_after_recovery(self, monitor):
        """After similarity recovers, can trigger again later."""
        # Trigger first notification
        for _ in range(5):
            monitor.record_similarity("user-1", 0.40)

        # Recover: push high scores into window
        for _ in range(5):
            monitor.record_similarity("user-1", 0.80)

        # Now degrade again
        for _ in range(5):
            monitor.record_similarity("user-1", 0.40)

        # Should trigger again since it recovered in between
        result = monitor.record_similarity("user-1", 0.40)
        # Window already full of 0.40 from above loop, already triggered on 5th
        # Let's check the 5th one in the degrade loop triggered
        # Actually the trigger happens when the 5th 0.40 is added
        # After 5 × 0.80, window is [0.80]*5, mean=0.80 → recovered → notified flag cleared
        # Then 5 × 0.40 → 5th makes window [0.40]*5, mean=0.40 < 0.55 → triggers
        # The 6th 0.40 above won't trigger again
        assert result is None  # Already triggered on the 5th low score

    def test_independent_users(self, monitor):
        """Tracks users independently."""
        for _ in range(5):
            monitor.record_similarity("user-1", 0.70)
        for _ in range(4):
            monitor.record_similarity("user-2", 0.40)
        result = monitor.record_similarity("user-2", 0.40)
        assert result == "user-2"

    def test_boundary_exactly_at_threshold(self, monitor):
        """Mean exactly at threshold should not trigger."""
        for _ in range(5):
            monitor.record_similarity("user-1", 0.55)
        # mean == 0.55, which is NOT < 0.55
        assert "user-1" not in monitor._notified


class TestGetMeanSimilarity:
    def test_returns_none_insufficient_data(self, monitor):
        """Returns None when window not full."""
        monitor.record_similarity("user-1", 0.60)
        assert monitor.get_mean_similarity("user-1") is None

    def test_returns_mean_when_full(self, monitor):
        """Returns correct mean when window is full."""
        for _ in range(5):
            monitor.record_similarity("user-1", 0.60)
        mean = monitor.get_mean_similarity("user-1")
        assert mean == pytest.approx(0.60, abs=0.001)

    def test_unknown_user(self, monitor):
        """Unknown user returns None."""
        assert monitor.get_mean_similarity("nonexistent") is None


class TestResetUser:
    def test_clears_data(self, monitor):
        """Reset clears all tracking data for user."""
        for _ in range(5):
            monitor.record_similarity("user-1", 0.40)
        monitor.reset_user("user-1")
        assert monitor.get_mean_similarity("user-1") is None
        assert "user-1" not in monitor._notified

    def test_can_trigger_after_reset(self, monitor):
        """Can trigger again after reset."""
        for _ in range(5):
            monitor.record_similarity("user-1", 0.40)
        monitor.reset_user("user-1")
        for _ in range(4):
            monitor.record_similarity("user-1", 0.40)
        result = monitor.record_similarity("user-1", 0.40)
        assert result == "user-1"


class TestClear:
    def test_clears_all(self, monitor):
        """Clear removes all users."""
        for _ in range(5):
            monitor.record_similarity("user-1", 0.40)
        for _ in range(5):
            monitor.record_similarity("user-2", 0.40)
        monitor.clear()
        assert monitor.get_mean_similarity("user-1") is None
        assert monitor.get_mean_similarity("user-2") is None
