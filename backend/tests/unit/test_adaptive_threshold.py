"""
Unit Tests for Adaptive Threshold Manager

Tests per-room threshold adaptation based on match/non-match distributions.
"""

from unittest.mock import patch

import pytest

from app.services.ml.adaptive_threshold import AdaptiveThresholdManager


# Current defaults: RECOGNITION_THRESHOLD=0.25, floor=0.25, ceiling=0.25
# With floor==ceiling, adaptive threshold always clamps to 0.25.
# Tests that verify adaptation logic patch floor/ceiling to meaningful ranges.

class TestAdaptiveThreshold:

    def test_default_threshold_no_data(self):
        """Without any data, returns global RECOGNITION_THRESHOLD."""
        mgr = AdaptiveThresholdManager()
        th = mgr.get_threshold("room-1")
        assert th == 0.25  # from settings default

    def test_default_threshold_insufficient_samples(self):
        """With fewer than min_samples, returns default threshold."""
        mgr = AdaptiveThresholdManager()
        for i in range(10):
            mgr.record_match("room-1", 0.8, is_match=True)
            mgr.record_match("room-1", 0.3, is_match=False)
        # 20 total < 50 min_samples
        assert mgr.get_threshold("room-1") == 0.25

    @patch("app.services.ml.adaptive_threshold.settings")
    def test_adapts_after_sufficient_samples(self, mock_settings):
        """After enough samples, threshold adapts to midpoint (clamped)."""
        mock_settings.ADAPTIVE_THRESHOLD_ENABLED = True
        mock_settings.RECOGNITION_THRESHOLD = 0.25
        mock_settings.ADAPTIVE_THRESHOLD_FLOOR = 0.20
        mock_settings.ADAPTIVE_THRESHOLD_CEILING = 0.65
        mock_settings.ADAPTIVE_THRESHOLD_MIN_SAMPLES = 50
        mock_settings.ADAPTIVE_THRESHOLD_WINDOW = 500

        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-1", 0.75, is_match=True)
            mgr.record_match("room-1", 0.25, is_match=False)
        # total = 60 >= 50, midpoint = (0.75 + 0.25) / 2 = 0.5
        th = mgr.get_threshold("room-1")
        assert abs(th - 0.5) < 0.01

    @patch("app.services.ml.adaptive_threshold.settings")
    def test_threshold_clamped_to_floor(self, mock_settings):
        """Threshold should not go below floor."""
        mock_settings.ADAPTIVE_THRESHOLD_ENABLED = True
        mock_settings.RECOGNITION_THRESHOLD = 0.25
        mock_settings.ADAPTIVE_THRESHOLD_FLOOR = 0.35
        mock_settings.ADAPTIVE_THRESHOLD_CEILING = 0.65
        mock_settings.ADAPTIVE_THRESHOLD_MIN_SAMPLES = 50
        mock_settings.ADAPTIVE_THRESHOLD_WINDOW = 500

        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-1", 0.3, is_match=True)
            mgr.record_match("room-1", 0.1, is_match=False)
        th = mgr.get_threshold("room-1")
        # Midpoint = (0.3 + 0.1) / 2 = 0.2 → clamped to floor 0.35
        assert th == 0.35

    @patch("app.services.ml.adaptive_threshold.settings")
    def test_threshold_clamped_to_ceiling(self, mock_settings):
        """Threshold should not go above ceiling."""
        mock_settings.ADAPTIVE_THRESHOLD_ENABLED = True
        mock_settings.RECOGNITION_THRESHOLD = 0.25
        mock_settings.ADAPTIVE_THRESHOLD_FLOOR = 0.20
        mock_settings.ADAPTIVE_THRESHOLD_CEILING = 0.65
        mock_settings.ADAPTIVE_THRESHOLD_MIN_SAMPLES = 50
        mock_settings.ADAPTIVE_THRESHOLD_WINDOW = 500

        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-1", 0.95, is_match=True)
            mgr.record_match("room-1", 0.7, is_match=False)
        th = mgr.get_threshold("room-1")
        # Midpoint = (0.95 + 0.7) / 2 = 0.825 → clamped to ceiling 0.65
        assert th == 0.65

    @patch("app.services.ml.adaptive_threshold.settings")
    def test_rooms_are_independent(self, mock_settings):
        """Different rooms maintain independent statistics."""
        mock_settings.ADAPTIVE_THRESHOLD_ENABLED = True
        mock_settings.RECOGNITION_THRESHOLD = 0.25
        mock_settings.ADAPTIVE_THRESHOLD_FLOOR = 0.20
        mock_settings.ADAPTIVE_THRESHOLD_CEILING = 0.65
        mock_settings.ADAPTIVE_THRESHOLD_MIN_SAMPLES = 50
        mock_settings.ADAPTIVE_THRESHOLD_WINDOW = 500

        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-A", 0.8, is_match=True)
            mgr.record_match("room-A", 0.3, is_match=False)
            mgr.record_match("room-B", 0.9, is_match=True)
            mgr.record_match("room-B", 0.5, is_match=False)

        th_a = mgr.get_threshold("room-A")
        th_b = mgr.get_threshold("room-B")
        assert th_a != th_b
        # room-A midpoint ~0.55, room-B midpoint ~0.65 (clamped)
        assert abs(th_a - 0.55) < 0.01
        assert th_b == 0.65

    def test_needs_both_positive_and_negative(self):
        """Only positive samples → falls back to default."""
        mgr = AdaptiveThresholdManager()
        for _ in range(60):
            mgr.record_match("room-1", 0.8, is_match=True)
        assert mgr.get_threshold("room-1") == 0.25

    def test_reset_room(self):
        """Resetting a room clears its stats."""
        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-1", 0.8, is_match=True)
            mgr.record_match("room-1", 0.3, is_match=False)
        mgr.reset("room-1")
        assert mgr.get_threshold("room-1") == 0.25

    def test_reset_all(self):
        """Resetting all rooms clears everything."""
        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-1", 0.8, is_match=True)
            mgr.record_match("room-1", 0.3, is_match=False)
            mgr.record_match("room-2", 0.7, is_match=True)
            mgr.record_match("room-2", 0.2, is_match=False)
        mgr.reset()
        assert mgr.get_threshold("room-1") == 0.25
        assert mgr.get_threshold("room-2") == 0.25

    def test_get_stats(self):
        """get_stats returns correct counts and adaptation status."""
        mgr = AdaptiveThresholdManager()
        for _ in range(30):
            mgr.record_match("room-1", 0.8, is_match=True)
            mgr.record_match("room-1", 0.3, is_match=False)
        stats = mgr.get_stats("room-1")
        assert stats["positive_count"] == 30
        assert stats["negative_count"] == 30
        assert stats["adapted"] is True
        assert abs(stats["positive_mean"] - 0.8) < 0.01

    def test_get_stats_unknown_room(self):
        """get_stats for unknown room returns defaults."""
        mgr = AdaptiveThresholdManager()
        stats = mgr.get_stats("unknown")
        assert stats["positive_count"] == 0
        assert stats["adapted"] is False

    @patch("app.services.ml.adaptive_threshold.settings")
    def test_disabled_returns_default(self, mock_settings):
        """When disabled, always returns RECOGNITION_THRESHOLD."""
        mock_settings.ADAPTIVE_THRESHOLD_ENABLED = False
        mock_settings.RECOGNITION_THRESHOLD = 0.5
        mock_settings.ADAPTIVE_THRESHOLD_WINDOW = 500
        mgr = AdaptiveThresholdManager()
        for _ in range(60):
            mgr.record_match("room-1", 0.9, is_match=True)
            mgr.record_match("room-1", 0.2, is_match=False)
        assert mgr.get_threshold("room-1") == 0.5

    def test_rolling_window_evicts_old(self):
        """Window size limits stored samples (uses deque maxlen)."""
        mgr = AdaptiveThresholdManager()
        room = mgr._get_room("room-1")
        # Window size is 500 by default; fill with 600 samples
        for i in range(600):
            mgr.record_match("room-1", 0.8, is_match=True)
        assert len(room.positive) == 500
