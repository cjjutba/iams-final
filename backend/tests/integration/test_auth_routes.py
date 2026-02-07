"""
Integration Tests for Authentication Routes

Exercises the full HTTP request/response cycle through FastAPI's TestClient
with a real SQLite test database backing the application. Tests cover
registration, login, token refresh, current-user retrieval, and
unauthorized access scenarios.
"""

import uuid

import pytest

from app.config import settings


API = settings.API_PREFIX


# ===================================================================
# Student Registration
# ===================================================================


class TestRegisterStudentRoute:
    """Tests for POST /api/v1/auth/register."""

    def test_register_student_success(self, client):
        """A valid registration request should return 201 with user + tokens."""
        payload = {
            "student_id": "STU-2024-100",
            "email": "newstudent@test.edu",
            "password": "StrongPass1",
            "first_name": "New",
            "last_name": "Student",
        }
        response = client.post(f"{API}/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["user"]["email"] == "newstudent@test.edu"
        assert data["user"]["role"] == "student"
        assert data["tokens"]["access_token"]
        assert data["tokens"]["token_type"] == "bearer"

    def test_register_student_duplicate_email(self, client):
        """Registering the same email twice should return an error."""
        payload = {
            "student_id": "STU-2024-101",
            "email": "duplicate@test.edu",
            "password": "StrongPass1",
            "first_name": "First",
            "last_name": "User",
        }
        # First registration succeeds
        resp1 = client.post(f"{API}/auth/register", json=payload)
        assert resp1.status_code == 201

        # Second registration with same email should fail
        payload["student_id"] = "STU-2024-102"
        resp2 = client.post(f"{API}/auth/register", json=payload)
        assert resp2.status_code in (400, 409)

    def test_register_student_duplicate_student_id(self, client):
        """Registering the same student_id twice should return an error."""
        base_payload = {
            "student_id": "STU-2024-103",
            "password": "StrongPass1",
            "first_name": "Test",
            "last_name": "User",
        }
        resp1 = client.post(f"{API}/auth/register", json={
            **base_payload, "email": "first103@test.edu"
        })
        assert resp1.status_code == 201

        resp2 = client.post(f"{API}/auth/register", json={
            **base_payload, "email": "second103@test.edu"
        })
        assert resp2.status_code in (400, 409)

    def test_register_student_missing_fields(self, client):
        """Omitting required fields should return 422."""
        response = client.post(f"{API}/auth/register", json={
            "student_id": "STU-2024-104"
        })
        assert response.status_code == 422

    def test_register_student_invalid_email(self, client):
        """An invalid email format should return 422."""
        payload = {
            "student_id": "STU-2024-105",
            "email": "not-an-email",
            "password": "StrongPass1",
            "first_name": "Test",
            "last_name": "User",
        }
        response = client.post(f"{API}/auth/register", json=payload)
        assert response.status_code == 422

    def test_register_student_short_password(self, client):
        """Password < 8 chars should be rejected at schema level (422)."""
        payload = {
            "student_id": "STU-2024-106",
            "email": "shortpw@test.edu",
            "password": "Short1",
            "first_name": "Test",
            "last_name": "User",
        }
        response = client.post(f"{API}/auth/register", json=payload)
        assert response.status_code == 422


# ===================================================================
# Login
# ===================================================================


class TestLoginRoute:
    """Tests for POST /api/v1/auth/login."""

    def _register_and_login(self, client, email, password, student_id):
        """Helper: register a student then attempt login."""
        client.post(f"{API}/auth/register", json={
            "student_id": student_id,
            "email": email,
            "password": password,
            "first_name": "Login",
            "last_name": "Test",
        })
        return client.post(f"{API}/auth/login", json={
            "identifier": email,
            "password": password,
        })

    def test_login_student_success_by_email(self, client):
        """Login with valid email + password should return 200 with tokens."""
        response = self._register_and_login(
            client, "logintest@test.edu", "StrongPass1", "STU-LOGIN-001"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "logintest@test.edu"

    def test_login_student_success_by_student_id(self, client):
        """Login using student_id as identifier should work."""
        # Register first
        client.post(f"{API}/auth/register", json={
            "student_id": "STU-LOGIN-002",
            "email": "sid_login@test.edu",
            "password": "StrongPass1",
            "first_name": "SID",
            "last_name": "Login",
        })
        response = client.post(f"{API}/auth/login", json={
            "identifier": "STU-LOGIN-002",
            "password": "StrongPass1",
        })
        assert response.status_code == 200

    def test_login_faculty_success(self, client, test_faculty):
        """Faculty login with email + password should succeed."""
        response = client.post(f"{API}/auth/login", json={
            "identifier": "faculty@test.jrmsu.edu.ph",
            "password": "TestPass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["role"] == "faculty"

    def test_login_wrong_password(self, client):
        """Login with an incorrect password should return 401."""
        # Register first
        client.post(f"{API}/auth/register", json={
            "student_id": "STU-LOGIN-003",
            "email": "wrongpw@test.edu",
            "password": "StrongPass1",
            "first_name": "Wrong",
            "last_name": "PW",
        })
        response = client.post(f"{API}/auth/login", json={
            "identifier": "wrongpw@test.edu",
            "password": "WrongPassword1",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Login for a user that does not exist should return 401."""
        response = client.post(f"{API}/auth/login", json={
            "identifier": "ghost@test.edu",
            "password": "AnyPassword1",
        })
        assert response.status_code == 401

    def test_login_inactive_user(self, client, inactive_student):
        """Login for an inactive user should return 401."""
        response = client.post(f"{API}/auth/login", json={
            "identifier": "inactive@test.jrmsu.edu.ph",
            "password": "TestPass123",
        })
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Omitting required login fields should return 422."""
        response = client.post(f"{API}/auth/login", json={
            "identifier": "test@test.edu",
        })
        assert response.status_code == 422


# ===================================================================
# Get Current User
# ===================================================================


class TestGetCurrentUserRoute:
    """Tests for GET /api/v1/auth/me."""

    def test_get_current_user_student(self, client, auth_headers_student, test_student):
        """Authenticated student should see their own profile."""
        response = client.get(f"{API}/auth/me", headers=auth_headers_student)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_student.email
        assert data["role"] == "student"
        assert data["first_name"] == test_student.first_name

    def test_get_current_user_faculty(self, client, auth_headers_faculty, test_faculty):
        """Authenticated faculty should see their own profile."""
        response = client.get(f"{API}/auth/me", headers=auth_headers_faculty)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_faculty.email
        assert data["role"] == "faculty"

    def test_unauthorized_access_no_token(self, client):
        """Request without Authorization header should return 401/403."""
        response = client.get(f"{API}/auth/me")
        assert response.status_code in (401, 403)

    def test_unauthorized_access_invalid_token(self, client):
        """Request with a garbage token should return 401."""
        response = client.get(
            f"{API}/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401

    def test_unauthorized_access_expired_token(self, client, test_student):
        """Request with an expired token should return 401."""
        from datetime import timedelta
        from app.utils.security import create_access_token

        expired_token = create_access_token(
            {"user_id": str(test_student.id)},
            expires_delta=timedelta(seconds=-1),
        )
        response = client.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401


# ===================================================================
# Token Refresh
# ===================================================================


class TestRefreshTokenRoute:
    """Tests for POST /api/v1/auth/refresh."""

    def test_refresh_token_success(self, client):
        """A valid refresh token should yield a new access token."""
        # Register to get tokens
        reg_resp = client.post(f"{API}/auth/register", json={
            "student_id": "STU-REFRESH-001",
            "email": "refresh@test.edu",
            "password": "StrongPass1",
            "first_name": "Refresh",
            "last_name": "Test",
        })
        assert reg_resp.status_code == 201
        refresh_token = reg_resp.json()["tokens"]["refresh_token"]

        # Use refresh token
        response = client.post(f"{API}/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_invalid(self, client):
        """An invalid refresh token should return 401."""
        response = client.post(f"{API}/auth/refresh", json={
            "refresh_token": "invalid.refresh.token",
        })
        assert response.status_code == 401


# ===================================================================
# Verify Student ID
# ===================================================================


class TestVerifyStudentIDRoute:
    """Tests for POST /api/v1/auth/verify-student-id."""

    def test_verify_student_id_valid(self, client):
        """A valid student ID should return valid=True."""
        response = client.post(f"{API}/auth/verify-student-id", json={
            "student_id": "STU-2024-001",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["student_info"]["student_id"] == "STU-2024-001"

    def test_verify_student_id_too_short(self, client):
        """A student ID < 3 chars should return valid=False."""
        response = client.post(f"{API}/auth/verify-student-id", json={
            "student_id": "AB",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_verify_student_id_empty_rejected_by_schema(self, client):
        """An empty student_id should be rejected at schema level (422)."""
        response = client.post(f"{API}/auth/verify-student-id", json={
            "student_id": "",
        })
        assert response.status_code == 422


# ===================================================================
# Logout
# ===================================================================


class TestLogoutRoute:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_success(self, client, auth_headers_student):
        """Authenticated user should get a success response on logout."""
        response = client.post(f"{API}/auth/logout", headers=auth_headers_student)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_logout_unauthenticated(self, client):
        """Unauthenticated logout attempt should return 401/403."""
        response = client.post(f"{API}/auth/logout")
        assert response.status_code in (401, 403)
