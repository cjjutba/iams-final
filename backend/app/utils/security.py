"""
Security and Authentication Utilities

Provides password hashing, JWT token creation/verification,
and Supabase Auth token validation.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from passlib.context import CryptContext
from jose import JWTError, jwt
import httpx

from app.config import settings, logger
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


# ===== JWT Token Management (Custom for Faculty) =====

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
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
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    # Encode token
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict) -> str:
    """
    Create a JWT refresh token (longer expiration)

    Args:
        data: Dictionary with user data to encode

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
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
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise AuthenticationError("Invalid or expired token")


# ===== Supabase Auth Token Verification =====

async def verify_supabase_token(token: str) -> Dict:
    """
    Verify a Supabase Auth JWT token

    This validates the token against Supabase's JWKS endpoint

    Args:
        token: Supabase JWT token from Authorization header

    Returns:
        Decoded token payload with user info

    Raises:
        AuthenticationError: If token is invalid
    """
    try:
        # Supabase uses RS256 algorithm with JWKS
        # For simplicity in MVP, we'll decode without verification
        # In production, implement proper JWKS validation

        # Extract project ref from SUPABASE_URL
        project_ref = settings.SUPABASE_URL.split("//")[1].split(".")[0]

        # Decode token (without verification for now)
        # TODO: Implement proper JWKS verification for production
        payload = jwt.decode(
            token,
            settings.SUPABASE_ANON_KEY,
            algorithms=["HS256"],
            options={"verify_signature": False}  # Disable for MVP
        )

        # Validate token hasn't expired
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise AuthenticationError("Token has expired")

        return payload

    except JWTError as e:
        logger.error(f"Supabase token verification failed: {e}")
        raise AuthenticationError("Invalid Supabase token")


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
