"""
Unit Tests for Analytics Service

Tests analytics queries using mock DB sessions.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import uuid

import pytest

from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.engagement_score import EngagementScore
from app.models.enrollment import Enrollment
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.services.analytics_service import AnalyticsService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def svc(mock_db):
    return AnalyticsService(mock_db)


class TestGetClassOverview:
    def test_empty_class(self, svc, mock_db):
        """No records → zero stats."""
        schedule = MagicMock(spec=Schedule)
        schedule.subject_code = "CS101"
        schedule.subject_name = "Intro to CS"
        mock_db.query.return_value.filter.return_value.first.return_value = schedule
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = svc.get_class_overview(str(uuid.uuid4()))
        assert result["total_sessions"] == 0

    def test_schedule_not_found(self, svc, mock_db):
        """Unknown schedule → empty dict."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = svc.get_class_overview(str(uuid.uuid4()))
        assert result == {}


class TestGetStudentDashboard:
    def test_no_records(self, svc, mock_db):
        """Student with no attendance → zero stats."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []

        result = svc.get_student_dashboard(str(uuid.uuid4()))
        assert result["overall_rate"] == 0.0
        assert result["classes_attended"] == 0
        assert result["current_streak"] == 0

    def test_perfect_attendance(self, svc, mock_db):
        """All present → 100% rate."""
        records = []
        for i in range(5):
            rec = MagicMock(spec=AttendanceRecord)
            rec.status = AttendanceStatus.PRESENT
            rec.date = date.today() - timedelta(days=i)
            rec.schedule_id = uuid.uuid4()
            records.append(rec)

        # First query for AttendanceRecord returns records
        mock_db.query.return_value.filter.return_value.all.return_value = records
        # EngagementScore join query
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []

        result = svc.get_student_dashboard(str(uuid.uuid4()))
        assert result["overall_rate"] == 100.0
        assert result["classes_attended"] == 5
        assert result["current_streak"] == 5


class TestGetSystemMetrics:
    def test_returns_all_fields(self, svc, mock_db):
        """Verify all expected fields are present."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.scalar.return_value = 0

        result = svc.get_system_metrics()
        assert "total_students" in result
        assert "total_faculty" in result
        assert "total_schedules" in result
        assert "total_attendance_records" in result
        assert "average_attendance_rate" in result
        assert "total_anomalies" in result
        assert "unresolved_anomalies" in result
        assert "total_early_leaves" in result


class TestGetAttendanceHeatmap:
    def test_empty_schedule(self, svc, mock_db):
        """No records → empty heatmap."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = svc.get_attendance_heatmap(str(uuid.uuid4()))
        assert result == []
