"""
Unit Tests for Anomaly Detection Service

Tests the four pure detector functions independently.
"""

import pytest

from app.models.attendance_anomaly import AnomalyType
from app.services.anomaly_service import (
    detect_sudden_absence,
    detect_proxy_suspect,
    detect_pattern_break,
    detect_low_confidence,
)


# ---------------------------------------------------------------------------
# Sudden Absence Detector
# ---------------------------------------------------------------------------

class TestDetectSuddenAbsence:
    def test_absent_with_high_history(self):
        """Student with 90% rate absent today → anomaly."""
        result = detect_sudden_absence(90.0, is_absent_today=True)
        assert result is not None
        assert result["anomaly_type"] == AnomalyType.SUDDEN_ABSENCE
        assert result["severity"] == "medium"

    def test_absent_with_very_high_history(self):
        """Student with 95%+ rate absent today → high severity."""
        result = detect_sudden_absence(98.0, is_absent_today=True)
        assert result is not None
        assert result["severity"] == "high"

    def test_absent_with_low_history(self):
        """Student with 60% rate absent → no anomaly (frequent absences)."""
        result = detect_sudden_absence(60.0, is_absent_today=True)
        assert result is None

    def test_present_with_high_history(self):
        """Student present → no anomaly regardless of history."""
        result = detect_sudden_absence(95.0, is_absent_today=False)
        assert result is None

    def test_custom_threshold(self):
        """Custom min_history_rate."""
        result = detect_sudden_absence(70.0, is_absent_today=True, min_history_rate=70.0)
        assert result is not None

    def test_at_boundary(self):
        """Exactly at threshold → triggers."""
        result = detect_sudden_absence(80.0, is_absent_today=True, min_history_rate=80.0)
        assert result is not None

    def test_just_below_boundary(self):
        """Just below threshold → no anomaly."""
        result = detect_sudden_absence(79.9, is_absent_today=True, min_history_rate=80.0)
        assert result is None


# ---------------------------------------------------------------------------
# Proxy Suspect Detector
# ---------------------------------------------------------------------------

class TestDetectProxySuspect:
    def test_two_rooms(self):
        """Same student in 2 rooms → anomaly."""
        sessions = [("sched-1", "Room 101"), ("sched-2", "Room 202")]
        result = detect_proxy_suspect(sessions)
        assert result is not None
        assert result["anomaly_type"] == AnomalyType.PROXY_SUSPECT
        assert result["severity"] == "high"
        assert "Room 101" in result["description"]
        assert "Room 202" in result["description"]

    def test_three_rooms(self):
        """Student in 3 rooms → anomaly with all rooms listed."""
        sessions = [
            ("s1", "Room A"), ("s2", "Room B"), ("s3", "Room C")
        ]
        result = detect_proxy_suspect(sessions)
        assert result is not None
        assert "3 rooms" in result["description"]

    def test_single_room(self):
        """Student in 1 room → no anomaly."""
        sessions = [("sched-1", "Room 101")]
        result = detect_proxy_suspect(sessions)
        assert result is None

    def test_empty_sessions(self):
        """No sessions → no anomaly."""
        result = detect_proxy_suspect([])
        assert result is None


# ---------------------------------------------------------------------------
# Pattern Break Detector
# ---------------------------------------------------------------------------

class TestDetectPatternBreak:
    def test_significant_drop(self):
        """Consistent 90%+ history, current 30% → anomaly."""
        weekly_rates = [90.0, 92.0, 88.0, 91.0]
        result = detect_pattern_break(weekly_rates, current_week_rate=30.0)
        assert result is not None
        assert result["anomaly_type"] == AnomalyType.PATTERN_BREAK

    def test_minor_fluctuation(self):
        """Normal variation within threshold → no anomaly."""
        weekly_rates = [80.0, 65.0, 90.0, 70.0]
        # std ~10.8, mean ~76.25, so 68% is only ~0.76 std devs below
        result = detect_pattern_break(weekly_rates, current_week_rate=68.0)
        assert result is None

    def test_not_enough_history(self):
        """Less than min_weeks → no anomaly."""
        weekly_rates = [90.0, 85.0]
        result = detect_pattern_break(weekly_rates, current_week_rate=20.0, min_weeks=3)
        assert result is None

    def test_consistent_student_sudden_drop(self):
        """Very consistent (low std) student drops → uses fixed std, triggers."""
        weekly_rates = [100.0, 100.0, 100.0, 100.0]
        result = detect_pattern_break(weekly_rates, current_week_rate=50.0)
        assert result is not None

    def test_high_severity_large_deviation(self):
        """Deviation >= 3 std devs → high severity."""
        weekly_rates = [90.0, 92.0, 88.0, 91.0]
        result = detect_pattern_break(weekly_rates, current_week_rate=10.0)
        assert result is not None
        assert result["severity"] == "high"

    def test_improvement_not_flagged(self):
        """Rate going UP is not an anomaly (only drops)."""
        weekly_rates = [50.0, 55.0, 48.0, 52.0]
        result = detect_pattern_break(weekly_rates, current_week_rate=90.0)
        assert result is None


# ---------------------------------------------------------------------------
# Low Confidence Detector
# ---------------------------------------------------------------------------

class TestDetectLowConfidence:
    def test_low_avg_confidence(self):
        """Average confidence below threshold → anomaly."""
        result = detect_low_confidence(0.35, threshold=0.5, scan_count=10)
        assert result is not None
        assert result["anomaly_type"] == AnomalyType.LOW_CONFIDENCE
        assert result["severity"] == "medium"

    def test_very_low_confidence(self):
        """Very low confidence → high severity."""
        result = detect_low_confidence(0.2, threshold=0.5, scan_count=5)
        assert result is not None
        assert result["severity"] == "high"

    def test_acceptable_confidence(self):
        """Above threshold → no anomaly."""
        result = detect_low_confidence(0.7, threshold=0.5, scan_count=10)
        assert result is None

    def test_at_threshold(self):
        """Exactly at threshold → no anomaly (not below)."""
        result = detect_low_confidence(0.5, threshold=0.5, scan_count=10)
        assert result is None

    def test_not_enough_scans(self):
        """Too few scans → no anomaly."""
        result = detect_low_confidence(0.3, threshold=0.5, scan_count=1, min_scans=3)
        assert result is None

    def test_borderline_severity(self):
        """Confidence between 0.4 and 0.5 → low severity."""
        result = detect_low_confidence(0.45, threshold=0.5, scan_count=5)
        assert result is not None
        assert result["severity"] == "low"
