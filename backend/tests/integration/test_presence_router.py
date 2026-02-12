"""
Integration Tests for the Presence Router

Tests all 6 endpoints in app/routers/presence.py via HTTP:

1. POST /api/v1/presence/sessions/start   - Start attendance session
2. POST /api/v1/presence/sessions/end     - End attendance session
3. GET  /api/v1/presence/sessions/active   - List active sessions
4. GET  /api/v1/presence/{attendance_id}/logs - Get presence logs
5. GET  /api/v1/presence/early-leaves      - Get early leave events
6. GET  /api/v1/presence/tracking/stats/{schedule_id} - Get tracking stats

IMPORTANT: PresenceService stores active_sessions as an instance variable.
Each HTTP request creates a new PresenceService(db) via the router, so session
state from previous requests is lost. This means:
  - start_session works (creates DB records, but instance state is discarded)
  - end_session always sees empty active_sessions -> returns 500 (the 404
    HTTPException from the router is caught by the generic except block and
    re-raised as 500)
  - get_active_sessions always returns empty list (fresh instance, no sessions)

Tests are designed to verify the HTTP layer: auth checks (401/403), request
validation, response schemas, and error handling.
"""

import uuid
from datetime import datetime, date

import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# Prefix used for all presence endpoints
# ============================================================
PREFIX = "/api/v1/presence"


# ============================================================
# 1. POST /sessions/start — Start Attendance Session
# ============================================================

class TestStartSession:
    """Tests for POST /api/v1/presence/sessions/start"""

    def test_start_session_faculty_success(
        self, client, auth_headers_faculty, test_schedule, test_enrollment
    ):
        """Faculty can start a session. Returns 200 with schedule_id,
        started_at, student_count, and message."""
        response = client.post(
            f"{PREFIX}/sessions/start",
            json={"schedule_id": str(test_schedule.id)},
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["schedule_id"] == str(test_schedule.id)
        assert "started_at" in data
        assert data["student_count"] >= 0
        assert "message" in data

    def test_start_session_admin_success(
        self, client, auth_headers_admin, test_schedule, test_enrollment
    ):
        """Admin can start a session (same permissions as faculty)."""
        response = client.post(
            f"{PREFIX}/sessions/start",
            json={"schedule_id": str(test_schedule.id)},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["schedule_id"] == str(test_schedule.id)

    def test_start_session_student_forbidden(
        self, client, auth_headers_student, test_schedule
    ):
        """Students cannot start sessions -- returns 403."""
        response = client.post(
            f"{PREFIX}/sessions/start",
            json={"schedule_id": str(test_schedule.id)},
            headers=auth_headers_student,
        )
        assert response.status_code == 403

    def test_start_session_unauthenticated(self, client, test_schedule):
        """No auth header -> 401."""
        response = client.post(
            f"{PREFIX}/sessions/start",
            json={"schedule_id": str(test_schedule.id)},
        )
        assert response.status_code == 401

    def test_start_session_schedule_not_found(self, client, auth_headers_faculty):
        """Non-existent schedule_id -> 404."""
        response = client.post(
            f"{PREFIX}/sessions/start",
            json={"schedule_id": str(uuid.uuid4())},
            headers=auth_headers_faculty,
        )
        assert response.status_code == 404


# ============================================================
# 2. POST /sessions/end — End Attendance Session
# ============================================================

class TestEndSession:
    """Tests for POST /api/v1/presence/sessions/end

    Due to the statelessness issue (each request creates a fresh
    PresenceService with empty active_sessions), end_session always
    sees no active session. The router raises HTTPException(404)
    inside a try/except that catches all Exceptions and re-wraps
    them as 500. So the expected status is 500 when no session is
    active.
    """

    def test_end_session_no_active_session(
        self, client, auth_headers_faculty, test_schedule
    ):
        """No active session -> 500 (see docstring above for why not 404)."""
        response = client.post(
            f"{PREFIX}/sessions/end",
            params={"schedule_id": str(test_schedule.id)},
            headers=auth_headers_faculty,
        )
        # The router catches its own HTTPException(404) in a generic except
        # block and re-raises as 500 with the original message embedded.
        assert response.status_code == 500
        assert "No active session" in response.json()["detail"]

    def test_end_session_student_forbidden(
        self, client, auth_headers_student, test_schedule
    ):
        """Students cannot end sessions -- returns 403."""
        response = client.post(
            f"{PREFIX}/sessions/end",
            params={"schedule_id": str(test_schedule.id)},
            headers=auth_headers_student,
        )
        assert response.status_code == 403

    def test_end_session_unauthenticated(self, client, test_schedule):
        """No auth header -> 401."""
        response = client.post(
            f"{PREFIX}/sessions/end",
            params={"schedule_id": str(test_schedule.id)},
        )
        assert response.status_code == 401


# ============================================================
# 3. GET /sessions/active — List Active Sessions
# ============================================================

class TestActiveSessions:
    """Tests for GET /api/v1/presence/sessions/active"""

    def test_get_active_sessions_faculty_empty(self, client, auth_headers_faculty):
        """Faculty gets empty list when no sessions are active.
        Due to PresenceService statelessness, this always returns
        an empty list."""
        response = client.get(
            f"{PREFIX}/sessions/active",
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        data = response.json()
        assert "active_sessions" in data
        assert "count" in data
        assert isinstance(data["active_sessions"], list)
        assert data["count"] == 0

    def test_get_active_sessions_admin(self, client, auth_headers_admin):
        """Admin can view active sessions."""
        response = client.get(
            f"{PREFIX}/sessions/active",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200

    def test_get_active_sessions_student_forbidden(
        self, client, auth_headers_student
    ):
        """Students cannot view active sessions -- returns 403."""
        response = client.get(
            f"{PREFIX}/sessions/active",
            headers=auth_headers_student,
        )
        assert response.status_code == 403

    def test_get_active_sessions_unauthenticated(self, client):
        """No auth header -> 401."""
        response = client.get(f"{PREFIX}/sessions/active")
        assert response.status_code == 401


# ============================================================
# 4. GET /{attendance_id}/logs — Get Presence Logs
# ============================================================

class TestPresenceLogs:
    """Tests for GET /api/v1/presence/{attendance_id}/logs"""

    def test_get_presence_logs_student_own_record(
        self, client, auth_headers_student, test_attendance_record
    ):
        """Student can view logs for their own attendance record.
        Returns empty list when no logs exist yet."""
        response = client.get(
            f"{PREFIX}/{test_attendance_record.id}/logs",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_presence_logs_faculty_can_view_any(
        self, client, auth_headers_faculty, test_attendance_record
    ):
        """Faculty can view presence logs for any attendance record."""
        response = client.get(
            f"{PREFIX}/{test_attendance_record.id}/logs",
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_presence_logs_with_data(
        self,
        client,
        auth_headers_student,
        test_attendance_record,
        db_session,
    ):
        """When presence logs exist, the endpoint returns them with
        correct schema fields (id, attendance_id, scan_number,
        scan_time, detected, confidence)."""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)
        repo.log_presence(str(test_attendance_record.id), {
            "scan_number": 1,
            "scan_time": datetime.now(),
            "detected": True,
            "confidence": 0.85,
        })
        repo.log_presence(str(test_attendance_record.id), {
            "scan_number": 2,
            "scan_time": datetime.now(),
            "detected": False,
            "confidence": None,
        })

        response = client.get(
            f"{PREFIX}/{test_attendance_record.id}/logs",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Verify schema fields on the first log
        log = data[0]
        assert "id" in log
        assert "attendance_id" in log
        assert "scan_number" in log
        assert "scan_time" in log
        assert "detected" in log
        assert "confidence" in log

        # First log was detected, second was not
        assert data[0]["detected"] is True
        assert data[0]["confidence"] == pytest.approx(0.85, abs=0.01)
        assert data[1]["detected"] is False

    def test_get_presence_logs_not_found(self, client, auth_headers_student):
        """Non-existent attendance_id -> 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"{PREFIX}/{fake_id}/logs",
            headers=auth_headers_student,
        )
        assert response.status_code == 404

    def test_get_presence_logs_student_other_record_forbidden(
        self,
        client,
        db_session,
        auth_headers_student,
        test_schedule,
    ):
        """Student cannot view logs for another student's attendance record."""
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        from app.models.attendance_record import AttendanceRecord, AttendanceStatus

        # Create another student
        other_student = User(
            id=uuid.uuid4(),
            email="other_student@test.jrmsu.edu.ph",
            password_hash=hash_password("TestPass123"),
            role=UserRole.STUDENT,
            first_name="Other",
            last_name="Student",
            student_id="STU-2024-999",
            is_active=True,
            email_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(other_student)
        db_session.commit()

        # Create attendance record for the other student
        other_record = AttendanceRecord(
            id=uuid.uuid4(),
            student_id=other_student.id,
            schedule_id=test_schedule.id,
            date=date.today(),
            status=AttendanceStatus.ABSENT,
            total_scans=0,
            scans_present=0,
            presence_score=0.0,
        )
        db_session.add(other_record)
        db_session.commit()

        response = client.get(
            f"{PREFIX}/{other_record.id}/logs",
            headers=auth_headers_student,
        )
        assert response.status_code == 403

    def test_get_presence_logs_unauthenticated(
        self, client, test_attendance_record
    ):
        """No auth header -> 401."""
        response = client.get(
            f"{PREFIX}/{test_attendance_record.id}/logs",
        )
        assert response.status_code == 401


# ============================================================
# 5. GET /early-leaves — Get Early Leave Events
# ============================================================

class TestEarlyLeaves:
    """Tests for GET /api/v1/presence/early-leaves"""

    def test_get_early_leaves_faculty_empty(self, client, auth_headers_faculty):
        """Faculty gets empty list when no early leave events exist."""
        response = client.get(
            f"{PREFIX}/early-leaves",
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_early_leaves_with_data(
        self,
        client,
        auth_headers_faculty,
        test_attendance_record,
        db_session,
    ):
        """When early leave events exist, they are returned with
        correct schema fields."""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)
        now = datetime.now()
        repo.create_early_leave_event({
            "attendance_id": str(test_attendance_record.id),
            "detected_at": now,
            "last_seen_at": now,
            "consecutive_misses": 3,
            "notified": False,
        })

        response = client.get(
            f"{PREFIX}/early-leaves",
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        event = data[0]
        assert "id" in event
        assert "attendance_id" in event
        assert "detected_at" in event
        assert "last_seen_at" in event
        assert event["consecutive_misses"] == 3
        assert event["notified"] is False

    def test_get_early_leaves_with_schedule_filter(
        self,
        client,
        auth_headers_faculty,
        test_attendance_record,
        test_schedule,
        db_session,
    ):
        """The schedule_id query parameter filters early leave events."""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)
        now = datetime.now()
        repo.create_early_leave_event({
            "attendance_id": str(test_attendance_record.id),
            "detected_at": now,
            "last_seen_at": now,
            "consecutive_misses": 4,
            "notified": False,
        })

        # Filter by the correct schedule_id -> should return the event
        response = client.get(
            f"{PREFIX}/early-leaves",
            params={"schedule_id": str(test_schedule.id)},
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Filter by a random schedule_id -> should return nothing
        response = client.get(
            f"{PREFIX}/early-leaves",
            params={"schedule_id": str(uuid.uuid4())},
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_get_early_leaves_student_forbidden(
        self, client, auth_headers_student
    ):
        """Students cannot access early leave reports -- returns 403."""
        response = client.get(
            f"{PREFIX}/early-leaves",
            headers=auth_headers_student,
        )
        assert response.status_code == 403

    def test_get_early_leaves_admin_allowed(self, client, auth_headers_admin):
        """Admin can access early leave reports."""
        response = client.get(
            f"{PREFIX}/early-leaves",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200

    def test_get_early_leaves_unauthenticated(self, client):
        """No auth header -> 401."""
        response = client.get(f"{PREFIX}/early-leaves")
        assert response.status_code == 401


# ============================================================
# 6. GET /tracking/stats/{schedule_id} — Get Tracking Stats
# ============================================================

class TestTrackingStats:
    """Tests for GET /api/v1/presence/tracking/stats/{schedule_id}

    This endpoint calls get_tracking_service() which returns the global
    TrackingService singleton. The singleton auto-initializes when first
    accessed, so no patching is strictly required for the happy path.
    """

    def test_get_tracking_stats_faculty(
        self, client, auth_headers_faculty, test_schedule
    ):
        """Faculty can view tracking stats. With no active tracking
        session the stats should all be zero."""
        response = client.get(
            f"{PREFIX}/tracking/stats/{test_schedule.id}",
            headers=auth_headers_faculty,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["schedule_id"] == str(test_schedule.id)
        assert "total_tracks" in data
        assert "confirmed_tracks" in data
        assert "identified_tracks" in data
        assert "unidentified_tracks" in data

        # No tracking session -> all zeros
        assert data["total_tracks"] == 0

    def test_get_tracking_stats_admin(
        self, client, auth_headers_admin, test_schedule
    ):
        """Admin can also view tracking stats."""
        response = client.get(
            f"{PREFIX}/tracking/stats/{test_schedule.id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200

    def test_get_tracking_stats_student_forbidden(
        self, client, auth_headers_student, test_schedule
    ):
        """Students cannot view tracking stats -- returns 403."""
        response = client.get(
            f"{PREFIX}/tracking/stats/{test_schedule.id}",
            headers=auth_headers_student,
        )
        assert response.status_code == 403

    def test_get_tracking_stats_unauthenticated(self, client, test_schedule):
        """No auth header -> 401."""
        response = client.get(
            f"{PREFIX}/tracking/stats/{test_schedule.id}",
        )
        assert response.status_code == 401
