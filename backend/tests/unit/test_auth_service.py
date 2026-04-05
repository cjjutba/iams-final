"""
Unit Tests for AuthService

Tests the authentication business logic layer with mocked repositories.
Each test method focuses on a single behaviour of AuthService so that
failures are easy to diagnose.
"""

import uuid
from datetime import datetime, date
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.auth_service import AuthService
from app.models.user import User, UserRole
from app.utils.exceptions import AuthenticationError, ValidationError, NotFoundError


# ===================================================================
# Helpers
# ===================================================================

def _make_user(
    *,
    role=UserRole.STUDENT,
    email="student@test.edu",
    password="TestPass123",
    student_id="STU-001",
    is_active=True,
    email_verified=True,
    supabase_user_id=None,
):
    """
    Build a mock User object that quacks like the SQLAlchemy model.

    The password_hash is generated from the supplied plain-text password
    so that ``verify_password(password, user.password_hash)`` returns True.
    """
    from app.utils.security import hash_password

    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = email
    user.password_hash = hash_password(password)
    user.role = role
    user.first_name = "Test"
    user.last_name = "User"
    user.student_id = student_id
    user.phone = None
    user.is_active = is_active
    user.email_verified = email_verified
    user.email_verified_at = datetime.utcnow() if email_verified else None
    user.supabase_user_id = supabase_user_id
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


_TEST_BIRTHDATE = date(2003, 5, 15)


def _make_student_record(student_id):
    """Build a mock StudentRecord for a given student_id."""
    record = MagicMock()
    record.student_id = student_id
    record.first_name = "Test"
    record.last_name = "Student"
    record.email = f"test@jrmsu.edu.ph"
    record.course = "BSCPE"
    record.year_level = 1
    record.section = "A"
    record.is_active = True
    record.birthdate = _TEST_BIRTHDATE
    record.contact_number = "09171234567"
    return record


def _make_auth_service(db_session=None):
    """
    Create an AuthService instance with mocked repositories.

    Mocks both user_repo and student_record_repo so that:
    - student_record_repo.get_by_student_id() returns a valid record by default
    - user_repo.get_by_student_id() returns None by default (not yet registered)

    Returns (service, mock_user_repo) so tests can configure repo return values.
    """
    if db_session is None:
        db_session = MagicMock()

    service = AuthService(db_session)
    service.user_repo = MagicMock()
    # Default: student not yet registered (neither student_id nor email)
    service.user_repo.get_by_student_id.return_value = None
    service.user_repo.get_by_email.return_value = None
    service.user_repo.get_by_student_id_or_email.return_value = None

    # Mock student_record_repo: returns a valid record for any ID by default
    mock_record_repo = MagicMock()
    mock_record_repo.get_by_student_id.side_effect = _make_student_record
    service.student_record_repo = mock_record_repo

    return service, service.user_repo


# ===================================================================
# verify_student_id
# ===================================================================


class TestVerifyStudentId:
    """Tests for AuthService.verify_student_id()."""

    def test_verify_student_id_valid(self):
        """A student ID with matching birthdate should be valid."""
        service, _ = _make_auth_service()
        result = service.verify_student_id("STU-2024-001", _TEST_BIRTHDATE)

        assert result["valid"] is True
        assert result["student_info"]["student_id"] == "STU-2024-001"
        assert "verified" in result["message"].lower() or "success" in result["message"].lower()

    def test_verify_student_id_valid_with_whitespace_padding(self):
        """Leading/trailing whitespace should be stripped and ID accepted."""
        service, _ = _make_auth_service()
        result = service.verify_student_id("  STU-001  ", _TEST_BIRTHDATE)

        assert result["valid"] is True
        assert result["student_info"]["student_id"] == "STU-001"

    def test_verify_student_id_empty(self):
        """An empty string should be invalid."""
        service, _ = _make_auth_service()
        result = service.verify_student_id("", _TEST_BIRTHDATE)

        assert result["valid"] is False
        assert result["student_info"] is None

    def test_verify_student_id_none(self):
        """None should be treated as invalid (falsy)."""
        service, _ = _make_auth_service()
        result = service.verify_student_id(None, _TEST_BIRTHDATE)

        assert result["valid"] is False

    def test_verify_student_id_too_short(self):
        """A student ID shorter than 3 characters (after stripping) should fail."""
        service, _ = _make_auth_service()
        result = service.verify_student_id("AB", _TEST_BIRTHDATE)

        assert result["valid"] is False
        assert "invalid" in result["message"].lower()

    def test_verify_student_id_whitespace_only(self):
        """An ID consisting only of whitespace should fail."""
        service, _ = _make_auth_service()
        result = service.verify_student_id("   ", _TEST_BIRTHDATE)

        assert result["valid"] is False

    def test_verify_student_id_exactly_three_chars(self):
        """A 3-character student ID should be accepted."""
        service, _ = _make_auth_service()
        result = service.verify_student_id("ABC", _TEST_BIRTHDATE)

        assert result["valid"] is True

    def test_verify_student_id_wrong_birthdate(self):
        """A valid student ID with wrong birthdate should fail."""
        service, _ = _make_auth_service()
        wrong_date = date(2000, 1, 1)
        result = service.verify_student_id("STU-2024-001", wrong_date)

        assert result["valid"] is False
        assert "verification failed" in result["message"].lower() or "birthdate" in result["message"].lower()


# ===================================================================
# login
# ===================================================================


class TestLogin:
    """Tests for AuthService.login()."""

    def test_login_success_with_email(self):
        """Successful login by email returns user and token dict."""
        service, repo = _make_auth_service()
        user = _make_user(email="student@test.edu", password="TestPass123")
        repo.get_by_identifier.return_value = user

        returned_user, tokens = service.login("student@test.edu", "TestPass123")

        assert returned_user == user
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        repo.get_by_identifier.assert_called_once_with("student@test.edu")

    def test_login_success_with_student_id(self):
        """Successful login by student ID returns user and tokens."""
        service, repo = _make_auth_service()
        user = _make_user(student_id="STU-001", password="TestPass123")
        repo.get_by_identifier.return_value = user

        returned_user, tokens = service.login("STU-001", "TestPass123")

        assert returned_user == user
        assert "access_token" in tokens

    def test_login_wrong_password(self):
        """Login with wrong password should raise AuthenticationError."""
        service, repo = _make_auth_service()
        user = _make_user(password="CorrectPassword1")
        repo.get_by_identifier.return_value = user

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            service.login("student@test.edu", "WrongPassword1")

    def test_login_user_not_found(self):
        """Login for a non-existent identifier should raise AuthenticationError."""
        service, repo = _make_auth_service()
        repo.get_by_identifier.return_value = None

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            service.login("nobody@test.edu", "AnyPassword1")

    def test_login_inactive_user(self):
        """Login for an inactive user should raise AuthenticationError."""
        service, repo = _make_auth_service()
        user = _make_user(password="TestPass123", is_active=False)
        repo.get_by_identifier.return_value = user

        with pytest.raises(AuthenticationError, match="inactive"):
            service.login("student@test.edu", "TestPass123")

    def test_login_returns_valid_jwt_tokens(self):
        """The returned tokens should be decodable JWTs with user_id."""
        from app.utils.security import verify_token

        service, repo = _make_auth_service()
        user = _make_user(password="TestPass123")
        repo.get_by_identifier.return_value = user

        _, tokens = service.login("student@test.edu", "TestPass123")

        access_payload = verify_token(tokens["access_token"])
        assert access_payload["user_id"] == str(user.id)

        refresh_payload = verify_token(tokens["refresh_token"])
        assert refresh_payload["user_id"] == str(user.id)
        assert refresh_payload["type"] == "refresh"


# ===================================================================
# register_student
# ===================================================================


class TestRegisterStudent:
    """Tests for AuthService.register_student()."""

    def test_register_student_success(self):
        """Valid registration data should create user and return tokens."""
        db_session = MagicMock()
        service, repo = _make_auth_service(db_session)

        reg_data = {
            "student_id": "STU-2024-001",
            "email": "new@test.edu",
            "password": "StrongPass1",
            "first_name": "New",
            "last_name": "Student",
            "phone": None,
        }

        user, tokens = service.register_student(reg_data)

        assert user.email == "new@test.edu"
        assert user.role == UserRole.STUDENT
        assert "access_token" in tokens
        db_session.add.assert_called()

    def test_register_student_invalid_student_id(self):
        """Registration with a student ID not in school records should raise."""
        service, _ = _make_auth_service()
        # Override mock: clear side_effect and return None (ID not found)
        service.student_record_repo.get_by_student_id.side_effect = None
        service.student_record_repo.get_by_student_id.return_value = None

        reg_data = {
            "student_id": "UNKNOWN-ID",
            "email": "new@test.edu",
            "password": "StrongPass1",
            "first_name": "New",
            "last_name": "Student",
        }

        with pytest.raises(ValidationError, match="not found"):
            service.register_student(reg_data)

    def test_register_student_weak_password(self):
        """Registration with a weak password should raise ValidationError."""
        service, _ = _make_auth_service()

        reg_data = {
            "student_id": "STU-2024-001",
            "email": "new@test.edu",
            "password": "short",  # Too short and no digit
            "first_name": "New",
            "last_name": "Student",
        }

        with pytest.raises(ValidationError):
            service.register_student(reg_data)

    def test_register_student_password_no_digit(self):
        """Registration with a password missing digits should raise."""
        service, _ = _make_auth_service()

        reg_data = {
            "student_id": "STU-2024-001",
            "email": "new@test.edu",
            "password": "NoDigitsHere",
            "first_name": "New",
            "last_name": "Student",
        }

        with pytest.raises(ValidationError, match="number"):
            service.register_student(reg_data)

    def test_register_student_calls_repo_with_hashed_password(self):
        """The password stored must be hashed, not plain."""
        db_session = MagicMock()
        service, repo = _make_auth_service(db_session)

        reg_data = {
            "student_id": "STU-2024-001",
            "email": "new@test.edu",
            "password": "StrongPass1",
            "first_name": "New",
            "last_name": "Student",
        }

        user, _ = service.register_student(reg_data)

        assert user.password_hash != "StrongPass1"
        assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")

    def test_register_student_sets_role_to_student(self):
        """The created user must have role = STUDENT."""
        db_session = MagicMock()
        service, repo = _make_auth_service(db_session)

        reg_data = {
            "student_id": "STU-2024-001",
            "email": "new@test.edu",
            "password": "StrongPass1",
            "first_name": "New",
            "last_name": "Student",
        }

        user, _ = service.register_student(reg_data)

        assert user.role == UserRole.STUDENT


# ===================================================================
# refresh_access_token
# ===================================================================


class TestRefreshAccessToken:
    """Tests for AuthService.refresh_access_token()."""

    def test_refresh_access_token_success(self):
        """A valid refresh token should yield a new access token."""
        from app.utils.security import create_refresh_token, verify_token

        service, repo = _make_auth_service()
        user = _make_user()
        repo.get_by_id.return_value = user

        refresh = create_refresh_token({"user_id": str(user.id)})
        result = service.refresh_access_token(refresh)

        assert "access_token" in result
        assert result["token_type"] == "bearer"
        # The new access token should be valid
        payload = verify_token(result["access_token"])
        assert payload["user_id"] == str(user.id)

    def test_refresh_access_token_with_access_token_fails(self):
        """Using an access token (no 'type' claim) should raise."""
        from app.utils.security import create_access_token

        service, _ = _make_auth_service()
        access = create_access_token({"user_id": "abc-123"})

        with pytest.raises(AuthenticationError):
            service.refresh_access_token(access)

    def test_refresh_access_token_invalid_token(self):
        """An invalid token string should raise AuthenticationError."""
        service, _ = _make_auth_service()

        with pytest.raises(AuthenticationError):
            service.refresh_access_token("not-a-valid-token")

    def test_refresh_access_token_inactive_user(self):
        """Refresh should fail if the user is now inactive."""
        from app.utils.security import create_refresh_token

        service, repo = _make_auth_service()
        user = _make_user(is_active=False)
        repo.get_by_id.return_value = user

        refresh = create_refresh_token({"user_id": str(user.id)})

        with pytest.raises(AuthenticationError):
            service.refresh_access_token(refresh)


# ===================================================================
# change_password
# ===================================================================


class TestChangePassword:
    """Tests for AuthService.change_password()."""

    def test_change_password_success(self):
        """Correct old password + valid new password should succeed."""
        service, repo = _make_auth_service()
        user = _make_user(password="OldPassword1")
        repo.get_by_id.return_value = user

        result = service.change_password(str(user.id), "OldPassword1", "NewPassword1")

        assert result is True
        repo.update.assert_called_once()

    def test_change_password_wrong_old_password(self):
        """Wrong old password should raise AuthenticationError."""
        service, repo = _make_auth_service()
        user = _make_user(password="OldPassword1")
        repo.get_by_id.return_value = user

        with pytest.raises(AuthenticationError, match="incorrect"):
            service.change_password(str(user.id), "WrongOld1", "NewPassword1")

    def test_change_password_weak_new_password(self):
        """A new password that fails strength checks should raise."""
        service, repo = _make_auth_service()
        user = _make_user(password="OldPassword1")
        repo.get_by_id.return_value = user

        with pytest.raises(ValidationError):
            service.change_password(str(user.id), "OldPassword1", "weak")

    def test_change_password_user_not_found(self):
        """Changing password for a non-existent user should raise."""
        service, repo = _make_auth_service()
        repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="User not found"):
            service.change_password("nonexistent-id", "OldPassword1", "NewPassword1")


# ===================================================================
# _generate_tokens (private but indirectly tested)
# ===================================================================


class TestGenerateTokens:
    """Tests for AuthService._generate_tokens() via login."""

    def test_tokens_contain_required_keys(self):
        """Token dict must have access_token, refresh_token, and token_type."""
        service, repo = _make_auth_service()
        user = _make_user(password="TestPass123")
        repo.get_by_identifier.return_value = user

        _, tokens = service.login("student@test.edu", "TestPass123")

        assert set(tokens.keys()) == {"access_token", "refresh_token", "token_type"}

    def test_token_type_is_bearer(self):
        """The token_type must always be 'bearer'."""
        service, repo = _make_auth_service()
        user = _make_user(password="TestPass123")
        repo.get_by_identifier.return_value = user

        _, tokens = service.login("student@test.edu", "TestPass123")

        assert tokens["token_type"] == "bearer"


# ===================================================================
# login - Supabase user (no password_hash)
# ===================================================================


class TestLoginSupabaseUser:
    """Test login behavior for users who only have Supabase auth (no local password)."""

    def test_login_no_password_hash_raises(self):
        """A user with password_hash=None should be rejected."""
        service, repo = _make_auth_service()
        user = _make_user(password="TestPass123")
        user.password_hash = None
        repo.get_by_identifier.return_value = user

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            service.login("student@test.edu", "AnyPassword1")


# ===================================================================
# forgot_password
# ===================================================================


class TestForgotPassword:
    """Tests for AuthService.forgot_password()."""

    def test_forgot_password_legacy_mode(self):
        """In legacy mode, forgot_password returns success message."""
        service, repo = _make_auth_service()
        repo.get_by_email.return_value = _make_user()

        result = service.forgot_password("student@test.edu")

        assert result["success"] is True
        assert "message" in result

    def test_forgot_password_unknown_email_returns_success(self):
        """Unknown email should return same success to prevent enumeration."""
        service, repo = _make_auth_service()
        repo.get_by_email.return_value = None

        result = service.forgot_password("unknown@test.edu")

        assert result["success"] is True
