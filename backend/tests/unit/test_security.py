"""
Unit Tests for Security Utilities

Tests password hashing, JWT token creation/verification, password strength
validation, and bearer token extraction.

These tests are pure unit tests with no database or network dependencies.
"""

import time as time_mod
from datetime import timedelta

import pytest
from jose import jwt

from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    validate_password_strength,
    extract_bearer_token,
    is_supabase_token,
    verify_supabase_token,
)
from app.utils.exceptions import AuthenticationError
from app.config import settings


# ===================================================================
# Password Hashing
# ===================================================================


class TestHashPassword:
    """Tests for hash_password()."""

    def test_hash_password_returns_string(self):
        """hash_password should return a non-empty string."""
        hashed = hash_password("MySecret123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_differs_from_plain(self):
        """The hash must not equal the original plain text."""
        plain = "MySecret123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_hash_password_is_bcrypt_format(self):
        """Bcrypt hashes start with '$2b$' (or '$2a$')."""
        hashed = hash_password("AnyPassword1")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_different_each_time(self):
        """Two hashes of the same password should differ (unique salts)."""
        h1 = hash_password("SamePassword1")
        h2 = hash_password("SamePassword1")
        assert h1 != h2


class TestVerifyPassword:
    """Tests for verify_password()."""

    def test_verify_password_correct(self):
        """verify_password should return True for the correct password."""
        plain = "CorrectHorse99"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password should return False for a wrong password."""
        hashed = hash_password("CorrectHorse99")
        assert verify_password("WrongPassword1", hashed) is False

    def test_verify_password_empty_plain(self):
        """verify_password should return False when plain text is empty."""
        hashed = hash_password("SomePassword1")
        assert verify_password("", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Password verification must be case-sensitive."""
        hashed = hash_password("CaseSensitive1")
        assert verify_password("casesensitive1", hashed) is False


# ===================================================================
# JWT Access Token
# ===================================================================


class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_create_access_token_returns_string(self):
        """Should return a non-empty JWT string."""
        token = create_access_token({"user_id": "abc-123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_user_data(self):
        """Decoded payload should contain the original data keys."""
        token = create_access_token({"user_id": "abc-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["user_id"] == "abc-123"

    def test_create_access_token_has_exp_claim(self):
        """Token must contain an 'exp' (expiration) claim."""
        token = create_access_token({"user_id": "abc-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_create_access_token_has_iat_claim(self):
        """Token must contain an 'iat' (issued-at) claim."""
        token = create_access_token({"user_id": "abc-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "iat" in payload

    def test_create_access_token_custom_expiry(self):
        """Custom expires_delta should be respected."""
        short_delta = timedelta(minutes=5)
        token = create_access_token({"user_id": "abc-123"}, expires_delta=short_delta)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # exp should be roughly 5 minutes from now, not the default 30 min
        assert payload["exp"] - payload["iat"] <= 5 * 60 + 5  # +5s tolerance

    def test_create_access_token_does_not_mutate_input(self):
        """The original data dict should not be modified."""
        data = {"user_id": "abc-123"}
        create_access_token(data)
        assert data == {"user_id": "abc-123"}


# ===================================================================
# JWT Refresh Token
# ===================================================================


class TestCreateRefreshToken:
    """Tests for create_refresh_token()."""

    def test_create_refresh_token_returns_string(self):
        """Should return a non-empty JWT string."""
        token = create_refresh_token({"user_id": "abc-123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_has_type_refresh(self):
        """Refresh tokens must include a 'type' = 'refresh' claim."""
        token = create_refresh_token({"user_id": "abc-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["type"] == "refresh"

    def test_create_refresh_token_longer_expiry_than_access(self):
        """Refresh token expiration must be longer than access token."""
        access = create_access_token({"user_id": "abc-123"})
        refresh = create_refresh_token({"user_id": "abc-123"})

        access_payload = jwt.decode(access, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        refresh_payload = jwt.decode(refresh, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert refresh_payload["exp"] > access_payload["exp"]

    def test_create_refresh_token_does_not_mutate_input(self):
        """The original data dict should not be modified."""
        data = {"user_id": "abc-123"}
        create_refresh_token(data)
        assert data == {"user_id": "abc-123"}


# ===================================================================
# Token Verification
# ===================================================================


class TestVerifyToken:
    """Tests for verify_token()."""

    def test_verify_token_valid(self):
        """A freshly created token should decode successfully."""
        token = create_access_token({"user_id": "abc-123"})
        payload = verify_token(token)
        assert payload["user_id"] == "abc-123"

    def test_verify_token_expired(self):
        """An expired token should raise AuthenticationError."""
        # Create a token that expired 1 second ago
        token = create_access_token(
            {"user_id": "abc-123"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            verify_token(token)

    def test_verify_token_invalid_string(self):
        """A garbage string should raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            verify_token("this.is.not.a.valid.jwt")

    def test_verify_token_wrong_secret(self):
        """A token signed with a different secret should fail verification."""
        token = jwt.encode(
            {"user_id": "abc-123", "exp": 9999999999},
            "wrong-secret-key",
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            verify_token(token)

    def test_verify_token_empty_string(self):
        """An empty string should raise AuthenticationError."""
        with pytest.raises(AuthenticationError):
            verify_token("")

    def test_verify_token_refresh_token_also_valid(self):
        """verify_token should also decode refresh tokens (same secret)."""
        token = create_refresh_token({"user_id": "abc-123"})
        payload = verify_token(token)
        assert payload["type"] == "refresh"
        assert payload["user_id"] == "abc-123"


# ===================================================================
# Password Strength Validation
# ===================================================================


class TestValidatePasswordStrength:
    """Tests for validate_password_strength()."""

    def test_validate_password_strength_valid(self):
        """A password meeting all requirements should pass."""
        is_valid, msg = validate_password_strength("StrongPass1")
        assert is_valid is True
        assert msg == ""

    def test_validate_password_strength_valid_with_special_chars(self):
        """Passwords with special characters should also pass."""
        is_valid, msg = validate_password_strength("C0mplex!@#$")
        assert is_valid is True

    def test_validate_password_strength_too_short(self):
        """Passwords shorter than 8 characters should fail."""
        is_valid, msg = validate_password_strength("Short1")
        assert is_valid is False
        assert "at least 8 characters" in msg

    def test_validate_password_strength_no_number(self):
        """Passwords without any digit should fail."""
        is_valid, msg = validate_password_strength("NoNumberHere")
        assert is_valid is False
        assert "at least one number" in msg

    def test_validate_password_strength_no_letter(self):
        """Passwords without any letter should fail."""
        is_valid, msg = validate_password_strength("12345678")
        assert is_valid is False
        assert "at least one letter" in msg

    def test_validate_password_strength_empty(self):
        """An empty password should fail the length check."""
        is_valid, msg = validate_password_strength("")
        assert is_valid is False

    def test_validate_password_strength_exactly_8_chars(self):
        """A password of exactly 8 chars meeting all rules should pass."""
        is_valid, msg = validate_password_strength("Abcdefg1")
        assert is_valid is True

    def test_validate_password_strength_only_spaces(self):
        """A password of only spaces should fail (no digit, no letter)."""
        is_valid, msg = validate_password_strength("        ")
        assert is_valid is False


# ===================================================================
# Bearer Token Extraction
# ===================================================================


class TestExtractBearerToken:
    """Tests for extract_bearer_token()."""

    def test_extract_bearer_token_valid(self):
        """Should extract the token from a valid 'Bearer <token>' header."""
        token = extract_bearer_token("Bearer my-jwt-token-here")
        assert token == "my-jwt-token-here"

    def test_extract_bearer_token_case_insensitive_scheme(self):
        """The 'Bearer' scheme check should be case-insensitive."""
        token = extract_bearer_token("bearer my-jwt-token-here")
        assert token == "my-jwt-token-here"

    def test_extract_bearer_token_missing_header(self):
        """Empty authorization string should raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Missing authorization header"):
            extract_bearer_token("")

    def test_extract_bearer_token_no_bearer_prefix(self):
        """Missing 'Bearer' prefix should raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Invalid authorization header format"):
            extract_bearer_token("Token my-jwt-token-here")

    def test_extract_bearer_token_no_token_value(self):
        """'Bearer' with no actual token should raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Invalid authorization header format"):
            extract_bearer_token("Bearer")

    def test_extract_bearer_token_extra_parts(self):
        """Authorization header with extra parts should raise AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Invalid authorization header format"):
            extract_bearer_token("Bearer token extra-stuff")


# ===================================================================
# Supabase Token Detection
# ===================================================================


class TestIsSupabaseToken:
    """Tests for is_supabase_token()."""

    def test_custom_jwt_not_supabase(self):
        """A custom JWT (no iss or aud claims) should return False."""
        token = create_access_token({"user_id": "abc-123"})
        assert is_supabase_token(token) is False

    def test_supabase_token_with_iss(self):
        """A JWT with 'supabase' in the iss claim should return True."""
        token = jwt.encode(
            {"sub": "user-id", "iss": "https://project.supabase.co/auth/v1", "exp": 9999999999},
            "some-secret",
            algorithm="HS256",
        )
        assert is_supabase_token(token) is True

    def test_supabase_token_with_aud(self):
        """A JWT with aud='authenticated' should return True."""
        token = jwt.encode(
            {"sub": "user-id", "aud": "authenticated", "exp": 9999999999},
            "some-secret",
            algorithm="HS256",
        )
        assert is_supabase_token(token) is True

    def test_invalid_token_returns_false(self):
        """A non-JWT string should return False (not crash)."""
        assert is_supabase_token("not-a-jwt") is False

    def test_empty_string_returns_false(self):
        """Empty string should return False."""
        assert is_supabase_token("") is False


# ===================================================================
# Supabase Token Verification
# ===================================================================


class TestVerifySupabaseToken:
    """Tests for verify_supabase_token()."""

    def test_verify_supabase_token_valid(self):
        """A valid Supabase-style token should decode successfully."""
        payload = {
            "sub": "user-uuid-123",
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
            "exp": 9999999999,
            "iat": 1000000000,
        }
        # When SUPABASE_JWT_SECRET is set, it's used for HS256 verification
        secret = settings.SUPABASE_JWT_SECRET if settings.SUPABASE_JWT_SECRET else "test-secret"
        token = jwt.encode(payload, secret, algorithm="HS256")

        result = verify_supabase_token(token)
        assert result["sub"] == "user-uuid-123"
        assert result["aud"] == "authenticated"

    def test_verify_supabase_token_invalid(self):
        """An invalid token should raise AuthenticationError."""
        with pytest.raises(AuthenticationError):
            verify_supabase_token("garbage-token-value")
