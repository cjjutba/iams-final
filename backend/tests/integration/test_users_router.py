"""
Integration tests for the users router (backend/app/routers/users.py).

Tests all 6 endpoints:
  GET    /api/v1/users/              - List users (admin only)
  GET    /api/v1/users/statistics    - User statistics (admin only)
  GET    /api/v1/users/{id}          - Get single user
  PATCH  /api/v1/users/{id}          - Update user
  DELETE /api/v1/users/{id}          - Deactivate user (admin only)
  POST   /api/v1/users/{id}/reactivate - Reactivate user (admin only)
"""

import pytest
from app.config import settings

PREFIX = settings.API_PREFIX


# ---------------------------------------------------------------------------
# TestListUsers
# ---------------------------------------------------------------------------
class TestListUsers:
    """GET /api/v1/users/ - admin only, with optional role/skip/limit filters."""

    def test_admin_list_all_users(self, client, auth_headers_admin, test_student, test_faculty, test_admin):
        """Admin should receive a list containing all seeded users."""
        response = client.get(f"{PREFIX}/users/", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # At least the three explicitly-created fixtures should be present
        returned_ids = {u["id"] for u in data}
        assert str(test_student.id) in returned_ids
        assert str(test_faculty.id) in returned_ids
        assert str(test_admin.id) in returned_ids

    def test_admin_filter_by_role(self, client, auth_headers_admin, test_student):
        """Filtering by role=student should only return student users."""
        response = client.get(f"{PREFIX}/users/?role=student", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert all(u["role"] == "student" for u in data)
        assert any(u["id"] == str(test_student.id) for u in data)

    def test_admin_pagination(self, client, auth_headers_admin):
        """skip and limit query params should control result window."""
        response = client.get(f"{PREFIX}/users/?skip=0&limit=1", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 1

    def test_non_admin_student_rejected(self, client, auth_headers_student):
        """Students must not be able to list all users."""
        response = client.get(f"{PREFIX}/users/", headers=auth_headers_student)
        assert response.status_code in (401, 403)

    def test_non_admin_faculty_rejected(self, client, auth_headers_faculty):
        """Faculty must not be able to list all users."""
        response = client.get(f"{PREFIX}/users/", headers=auth_headers_faculty)
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# TestGetUserStatistics
# ---------------------------------------------------------------------------
class TestGetUserStatistics:
    """GET /api/v1/users/statistics - admin only."""

    def test_admin_gets_statistics(self, client, auth_headers_admin):
        """Admin should receive a dict with user count information."""
        response = client.get(f"{PREFIX}/users/statistics", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_student_rejected(self, client, auth_headers_student):
        """Students cannot access user statistics."""
        response = client.get(f"{PREFIX}/users/statistics", headers=auth_headers_student)
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# TestGetUser
# ---------------------------------------------------------------------------
class TestGetUser:
    """GET /api/v1/users/{id} - students own profile only; faculty/admin any."""

    def test_student_views_own_profile(self, client, auth_headers_student, test_student):
        """A student should be able to retrieve their own profile."""
        response = client.get(
            f"{PREFIX}/users/{str(test_student.id)}", headers=auth_headers_student
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_student.id)

    def test_student_cannot_view_other_user(self, client, auth_headers_student, test_faculty):
        """A student must be forbidden from viewing another user's profile."""
        response = client.get(
            f"{PREFIX}/users/{str(test_faculty.id)}", headers=auth_headers_student
        )
        assert response.status_code == 403

    def test_faculty_can_view_any_user(self, client, auth_headers_faculty, test_student):
        """Faculty should be able to view any user's profile."""
        response = client.get(
            f"{PREFIX}/users/{str(test_student.id)}", headers=auth_headers_faculty
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_student.id)

    def test_admin_can_view_any_user(self, client, auth_headers_admin, test_student):
        """Admin should be able to view any user's profile."""
        response = client.get(
            f"{PREFIX}/users/{str(test_student.id)}", headers=auth_headers_admin
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_student.id)


# ---------------------------------------------------------------------------
# TestUpdateUser
# ---------------------------------------------------------------------------
class TestUpdateUser:
    """PATCH /api/v1/users/{id} - students own profile only."""

    def test_student_updates_own_profile(self, client, auth_headers_student, test_student):
        """A student should be able to update their own allowed fields."""
        payload = {"first_name": "UpdatedFirst", "last_name": "UpdatedLast"}
        response = client.patch(
            f"{PREFIX}/users/{str(test_student.id)}",
            json=payload,
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "UpdatedFirst"
        assert data["last_name"] == "UpdatedLast"

    def test_student_cannot_update_other_user(self, client, auth_headers_student, test_faculty):
        """A student must be forbidden from updating another user."""
        payload = {"first_name": "Hacked"}
        response = client.patch(
            f"{PREFIX}/users/{str(test_faculty.id)}",
            json=payload,
            headers=auth_headers_student,
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# TestDeactivateUser
# ---------------------------------------------------------------------------
class TestDeactivateUser:
    """DELETE /api/v1/users/{id} - admin only (soft-delete / deactivate)."""

    def test_admin_can_deactivate_user(self, client, auth_headers_admin, test_student):
        """Admin should be able to deactivate a user account."""
        response = client.delete(
            f"{PREFIX}/users/{str(test_student.id)}", headers=auth_headers_admin
        )
        assert response.status_code == 200

    def test_student_cannot_deactivate(self, client, auth_headers_student, test_faculty):
        """Students must not be able to deactivate any user."""
        response = client.delete(
            f"{PREFIX}/users/{str(test_faculty.id)}", headers=auth_headers_student
        )
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# TestReactivateUser
# ---------------------------------------------------------------------------
class TestReactivateUser:
    """POST /api/v1/users/{id}/reactivate - admin only."""

    def test_admin_can_reactivate_user(self, client, auth_headers_admin, inactive_student):
        """Admin should be able to reactivate a previously deactivated user."""
        response = client.post(
            f"{PREFIX}/users/{str(inactive_student.id)}/reactivate",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200

    def test_student_cannot_reactivate(self, client, auth_headers_student, inactive_student):
        """Students must not be able to reactivate users."""
        response = client.post(
            f"{PREFIX}/users/{str(inactive_student.id)}/reactivate",
            headers=auth_headers_student,
        )
        assert response.status_code in (401, 403)
