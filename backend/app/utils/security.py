"""
Security and Authentication Utilities

Provides password hashing, JWT token creation/verification,
and utility functions for authentication.
"""

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from app.config import logger, settings
from app.utils.exceptions import AuthenticationError

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ===== Password Hashing =====


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# ===== JWT Token Management (Custom JWT) =====


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary with user data to encode (e.g., {"user_id": "123"})
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    # Set expiration
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})

    # Encode token
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token (longer expiration)

    Args:
        data: Dictionary with user data to encode

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError as e:
        logger.debug("JWT token expired")
        raise AuthenticationError("Token expired") from e
    except InvalidTokenError as e:
        logger.error(f"JWT verification failed: {e}")
        raise AuthenticationError(f"Invalid token: {e}") from e



# ===== Utility Functions =====


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets security requirements

    Requirements:
    - At least 8 characters
    - Contains at least one number
    - Contains at least one letter

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number"

    if not any(char.isalpha() for char in password):
        return False, "Password must contain at least one letter"

    return True, ""


def extract_bearer_token(authorization: str) -> str:
    """
    Extract token from Authorization header

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        Extracted token string

    Raises:
        AuthenticationError: If header format is invalid
    """
    if not authorization:
        raise AuthenticationError("Missing authorization header")

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid authorization header format")

    return parts[1]
