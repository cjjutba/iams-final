"""
Unit Tests for Predictive Attendance Service

Tests EWMA computation, trend analysis, and risk classification.
"""

import pytest

from app.models.attendance_prediction import RiskLevel
from app.services.prediction_service import (
    compute_ewma,
    compute_trend,
    classify_risk,
    predict_next_week,
)


# ---------------------------------------------------------------------------
# EWMA
# ---------------------------------------------------------------------------

class TestComputeEWMA:
    def test_single_value(self):
        assert compute_ewma([80.0]) == 80.0

    def test_empty(self):
        assert compute_ewma([]) == 0.0

    def test_constant_rates(self):
        """Constant rates → EWMA equals that constant."""
        rates = [75.0, 75.0, 75.0, 75.0]
        assert abs(compute_ewma(rates) - 75.0) < 0.1

    def test_recent_weight(self):
        """Recent values should have more weight with alpha=0.3."""
        rates = [90.0, 90.0, 90.0, 50.0]
        ewma = compute_ewma(rates, alpha=0.3)
        # EWMA should be pulled toward 50 but not fully
        assert 50.0 < ewma < 90.0

    def test_high_alpha_more_responsive(self):
        """Higher alpha → more responsive to recent changes."""
        rates = [80.0, 80.0, 80.0, 40.0]
        low_alpha = compute_ewma(rates, alpha=0.1)
        high_alpha = compute_ewma(rates, alpha=0.9)
        # High alpha should be closer to 40 (the recent value)
        assert high_alpha < low_alpha

    def test_increasing_rates(self):
        """Increasing rates → EWMA trends upward."""
        rates = [60.0, 65.0, 70.0, 75.0, 80.0]
        ewma = compute_ewma(rates, alpha=0.3)
        assert ewma > 70.0  # Should be above midpoint

    def test_two_values(self):
        """Two values: EWMA = alpha * last + (1-alpha) * first."""
        ewma = compute_ewma([100.0, 0.0], alpha=0.5)
        assert abs(ewma - 50.0) < 0.1


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------

class TestComputeTrend:
    def test_improving_trend(self):
        """Steadily increasing rates → improving."""
        rates = [50.0, 55.0, 60.0, 65.0, 70.0]
        trend, slope = compute_trend(rates)
        assert trend == "improving"
        assert slope > 0

    def test_declining_trend(self):
        """Steadily decreasing rates → declining."""
        rates = [90.0, 85.0, 80.0, 75.0, 70.0]
        trend, slope = compute_trend(rates)
        assert trend == "declining"
        assert slope < 0

    def test_stable_trend(self):
        """Flat rates → stable."""
        rates = [75.0, 76.0, 74.0, 75.0, 75.5]
        trend, slope = compute_trend(rates)
        assert trend == "stable"
        assert abs(slope) < 2.0

    def test_not_enough_data(self):
        """Less than min_points → stable with 0 slope."""
        trend, slope = compute_trend([80.0, 70.0], min_points=3)
        assert trend == "stable"
        assert slope == 0.0

    def test_empty(self):
        trend, slope = compute_trend([])
        assert trend == "stable"
        assert slope == 0.0


# ---------------------------------------------------------------------------
# Risk Classification
# ---------------------------------------------------------------------------

class TestClassifyRisk:
    def test_critical(self):
        assert classify_risk(30.0) == RiskLevel.CRITICAL
        assert classify_risk(49.9) == RiskLevel.CRITICAL

    def test_high(self):
        assert classify_risk(50.0) == RiskLevel.HIGH
        assert classify_risk(64.9) == RiskLevel.HIGH

    def test_moderate(self):
        assert classify_risk(65.0) == RiskLevel.MODERATE
        assert classify_risk(79.9) == RiskLevel.MODERATE

    def test_low(self):
        assert classify_risk(80.0) == RiskLevel.LOW
        assert classify_risk(100.0) == RiskLevel.LOW

    def test_zero(self):
        assert classify_risk(0.0) == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Combined Prediction
# ---------------------------------------------------------------------------

class TestPredictNextWeek:
    def test_healthy_student(self):
        """Student with consistent 90% → low risk."""
        rates = [90.0, 88.0, 92.0, 90.0]
        pred = predict_next_week(rates)
        assert pred["risk_level"] == RiskLevel.LOW
        assert pred["predicted_rate"] > 85.0
        assert pred["trend"] == "stable"

    def test_declining_student(self):
        """Student trending down → higher risk."""
        rates = [95.0, 85.0, 75.0, 65.0, 55.0]
        pred = predict_next_week(rates)
        assert pred["risk_level"] in (RiskLevel.HIGH, RiskLevel.MODERATE)
        assert pred["trend"] == "declining"

    def test_improving_student(self):
        """Student trending up → improving trend."""
        rates = [40.0, 50.0, 60.0, 70.0, 80.0]
        pred = predict_next_week(rates)
        assert pred["trend"] == "improving"

    def test_clamped_to_range(self):
        """Predictions clamped to [0, 100]."""
        pred = predict_next_week([100.0, 100.0, 100.0])
        assert pred["predicted_rate"] <= 100.0
        pred = predict_next_week([0.0, 0.0, 0.0])
        assert pred["predicted_rate"] >= 0.0
