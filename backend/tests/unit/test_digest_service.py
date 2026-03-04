"""
Unit Tests for Digest Service

Tests the pure digest builder functions.
"""

import pytest

from app.services.digest_service import (
    build_faculty_daily_digest,
    build_student_weekly_digest,
)


class TestBuildFacultyDailyDigest:
    def test_normal_day(self):
        digest = build_faculty_daily_digest(
            total_classes=3,
            attendance_rates=[85.0, 90.0, 78.0],
            anomaly_count=1,
            early_leave_count=2,
        )
        assert digest["digest_type"] == "faculty_daily"
        assert digest["total_classes"] == 3
        assert abs(digest["average_attendance_rate"] - 84.3) < 0.1
        assert digest["anomaly_count"] == 1
        assert digest["early_leave_count"] == 2
        assert "3 classes" in digest["summary_text"]
        assert "1 anomalies" in digest["summary_text"]

    def test_no_classes(self):
        digest = build_faculty_daily_digest(
            total_classes=0,
            attendance_rates=[],
            anomaly_count=0,
            early_leave_count=0,
        )
        assert digest["total_classes"] == 0
        assert digest["average_attendance_rate"] == 0.0

    def test_perfect_day(self):
        digest = build_faculty_daily_digest(
            total_classes=2,
            attendance_rates=[100.0, 100.0],
            anomaly_count=0,
            early_leave_count=0,
        )
        assert digest["average_attendance_rate"] == 100.0
        assert "anomalies" not in digest["summary_text"]
        assert "early leaves" not in digest["summary_text"]


class TestBuildStudentWeeklyDigest:
    def test_normal_week(self):
        digest = build_student_weekly_digest(
            attendance_rate=85.0,
            classes_attended=17,
            classes_total=20,
            subject_breakdown=[
                {"schedule_id": "s1", "rate": 100.0, "attended": 5, "total": 5},
                {"schedule_id": "s2", "rate": 60.0, "attended": 3, "total": 5},
            ],
        )
        assert digest["digest_type"] == "student_weekly"
        assert digest["attendance_rate"] == 85.0
        assert digest["classes_attended"] == 17
        assert digest["classes_total"] == 20
        assert len(digest["subject_breakdown"]) == 2
        assert "17/20" in digest["summary_text"]

    def test_perfect_week(self):
        digest = build_student_weekly_digest(
            attendance_rate=100.0,
            classes_attended=10,
            classes_total=10,
            subject_breakdown=[],
        )
        assert digest["attendance_rate"] == 100.0
        assert "100%" in digest["summary_text"]

    def test_zero_week(self):
        digest = build_student_weekly_digest(
            attendance_rate=0.0,
            classes_attended=0,
            classes_total=5,
            subject_breakdown=[],
        )
        assert digest["attendance_rate"] == 0.0
        assert "0/5" in digest["summary_text"]
