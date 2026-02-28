"""
Integration tests for the schedules router.

Tests all 7 endpoints:
  GET    /api/v1/schedules/              - List all schedules
  GET    /api/v1/schedules/me            - My schedules (role-based)
  GET    /api/v1/schedules/{id}          - Get schedule by ID
  GET    /api/v1/schedules/{id}/students - Get enrolled students
  POST   /api/v1/schedules/             - Create schedule (admin only)
  PATCH  /api/v1/schedules/{id}         - Update schedule (admin only)
  DELETE /api/v1/schedules/{id}         - Delete schedule (admin only)
"""

import uuid

import pytest

from app.config import settings

API = settings.API_PREFIX


# ---------------------------------------------------------------------------
# TestListSchedules
# ---------------------------------------------------------------------------
class TestListSchedules:
    """GET /api/v1/schedules/ - list all schedules with optional day filter."""

    def test_list_schedules_returns_all(
        self, client, auth_headers_student, test_schedule
    ):
        """Authenticated user can list all active schedules."""
        resp = client.get(f"{API}/schedules/", headers=auth_headers_student)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        ids = [s["id"] for s in data]
        assert str(test_schedule.id) in ids

    def test_list_schedules_filter_by_day(
        self, client, auth_headers_student, test_schedule
    ):
        """Filter schedules by day_of_week query parameter returns only matching day."""
        target_day = test_schedule.day_of_week
        resp = client.get(
            f"{API}/schedules/",
            headers=auth_headers_student,
            params={"day": target_day},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for s in data:
            assert s["day_of_week"] == target_day

    def test_list_schedules_unauthenticated_returns_401(self, client):
        """Unauthenticated request is rejected with 401."""
        resp = client.get(f"{API}/schedules/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestGetMySchedules
# ---------------------------------------------------------------------------
class TestGetMySchedules:
    """GET /api/v1/schedules/me - returns schedules based on caller role."""

    def test_faculty_sees_teaching_schedules(
        self, client, auth_headers_faculty, test_schedule
    ):
        """Faculty user sees schedules they are assigned to teach."""
        resp = client.get(f"{API}/schedules/me", headers=auth_headers_faculty)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        ids = [s["id"] for s in data]
        assert str(test_schedule.id) in ids

    def test_student_sees_enrolled_schedules(
        self, client, auth_headers_student, test_enrollment
    ):
        """Student user sees only the schedules they are enrolled in."""
        resp = client.get(f"{API}/schedules/me", headers=auth_headers_student)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        ids = [s["id"] for s in data]
        assert str(test_enrollment.schedule_id) in ids

    def test_admin_sees_all_schedules(
        self, client, auth_headers_admin, test_schedule
    ):
        """Admin user sees all active schedules in the system."""
        resp = client.get(f"{API}/schedules/me", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1


# ---------------------------------------------------------------------------
# TestGetScheduleById
# ---------------------------------------------------------------------------
class TestGetScheduleById:
    """GET /api/v1/schedules/{id} - retrieve a single schedule."""

    def test_get_schedule_by_id_success(
        self, client, auth_headers_student, test_schedule
    ):
        """Returns the schedule when a valid ID is provided."""
        schedule_id = str(test_schedule.id)
        resp = client.get(
            f"{API}/schedules/{schedule_id}", headers=auth_headers_student
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == schedule_id
        assert data["subject_code"] == test_schedule.subject_code

    def test_get_schedule_by_id_not_found(
        self, client, auth_headers_student
    ):
        """Returns 404 when the schedule ID does not exist."""
        fake_id = str(uuid.uuid4())
        resp = client.get(
            f"{API}/schedules/{fake_id}", headers=auth_headers_student
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestGetEnrolledStudents
# ---------------------------------------------------------------------------
class TestGetEnrolledStudents:
    """GET /api/v1/schedules/{id}/students - list enrolled students."""

    def test_faculty_can_see_enrolled_students(
        self, client, auth_headers_faculty, test_schedule, test_enrollment
    ):
        """Faculty can retrieve the schedule with its enrolled students."""
        schedule_id = str(test_schedule.id)
        resp = client.get(
            f"{API}/schedules/{schedule_id}/students",
            headers=auth_headers_faculty,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Response is a ScheduleWithStudents object (not a plain list)
        assert data["id"] == schedule_id
        assert "enrolled_students" in data
        assert isinstance(data["enrolled_students"], list)
        assert len(data["enrolled_students"]) >= 1

    def test_student_cannot_see_enrolled_students(
        self, client, auth_headers_student, test_schedule
    ):
        """Students are forbidden from viewing enrolled student lists."""
        schedule_id = str(test_schedule.id)
        resp = client.get(
            f"{API}/schedules/{schedule_id}/students",
            headers=auth_headers_student,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestCreateSchedule
# ---------------------------------------------------------------------------
class TestCreateSchedule:
    """POST /api/v1/schedules/ - create a new schedule (admin only)."""

    def test_admin_can_create_schedule(
        self, client, auth_headers_admin, test_faculty, test_room
    ):
        """Admin can create a new schedule with valid payload."""
        payload = {
            "subject_code": "CPE401",
            "subject_name": "Embedded Systems",
            "day_of_week": 2,
            "start_time": "08:00:00",
            "end_time": "10:00:00",
            "semester": "2nd",
            "academic_year": "2024-2025",
            "faculty_id": str(test_faculty.id),
            "room_id": str(test_room.id),
        }
        resp = client.post(
            f"{API}/schedules/", headers=auth_headers_admin, json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_code"] == "CPE401"
        assert data["subject_name"] == "Embedded Systems"
        assert data["faculty_id"] == str(test_faculty.id)
        assert data["room_id"] == str(test_room.id)

    def test_student_cannot_create_schedule(
        self, client, auth_headers_student, test_faculty, test_room
    ):
        """Students are forbidden from creating schedules."""
        payload = {
            "subject_code": "CPE401",
            "subject_name": "Embedded Systems",
            "day_of_week": 2,
            "start_time": "08:00:00",
            "end_time": "10:00:00",
            "semester": "2nd",
            "academic_year": "2024-2025",
            "faculty_id": str(test_faculty.id),
            "room_id": str(test_room.id),
        }
        resp = client.post(
            f"{API}/schedules/", headers=auth_headers_student, json=payload
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestUpdateSchedule
# ---------------------------------------------------------------------------
class TestUpdateSchedule:
    """PATCH /api/v1/schedules/{id} - update a schedule (admin only)."""

    def test_admin_can_update_schedule(
        self, client, auth_headers_admin, test_schedule
    ):
        """Admin can partially update a schedule."""
        schedule_id = str(test_schedule.id)
        payload = {"subject_name": "Advanced Microprocessors"}
        resp = client.patch(
            f"{API}/schedules/{schedule_id}",
            headers=auth_headers_admin,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_name"] == "Advanced Microprocessors"

    def test_student_cannot_update_schedule(
        self, client, auth_headers_student, test_schedule
    ):
        """Students are forbidden from updating schedules."""
        schedule_id = str(test_schedule.id)
        payload = {"subject_name": "Hacked Name"}
        resp = client.patch(
            f"{API}/schedules/{schedule_id}",
            headers=auth_headers_student,
            json=payload,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestDeleteSchedule
# ---------------------------------------------------------------------------
class TestDeleteSchedule:
    """DELETE /api/v1/schedules/{id} - soft-delete a schedule (admin only)."""

    def test_admin_can_delete_schedule(
        self, client, auth_headers_admin, test_schedule
    ):
        """Admin can soft-delete a schedule; it no longer appears in active listings."""
        schedule_id = str(test_schedule.id)
        resp = client.delete(
            f"{API}/schedules/{schedule_id}", headers=auth_headers_admin
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # The soft-deleted schedule should no longer appear in the active list
        list_resp = client.get(
            f"{API}/schedules/", headers=auth_headers_admin
        )
        assert list_resp.status_code == 200
        active_ids = [s["id"] for s in list_resp.json()]
        assert schedule_id not in active_ids

    def test_student_cannot_delete_schedule(
        self, client, auth_headers_student, test_schedule
    ):
        """Students are forbidden from deleting schedules."""
        schedule_id = str(test_schedule.id)
        resp = client.delete(
            f"{API}/schedules/{schedule_id}", headers=auth_headers_student
        )
        assert resp.status_code == 403
