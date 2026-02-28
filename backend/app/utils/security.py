"""
Security and Authentication Utilities

Provides password hashing, JWT token creation/verification,
and Supabase Auth token validation.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from passlib.context import CryptContext
from jose import JWTError, jwt

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


# ===== JWT Token Management (Custom JWT) =====

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

def verify_supabase_token(token: str) -> Dict:
    """
    Verify a Supabase Auth JWT token.

    When SUPABASE_JWT_SECRET is configured, the token signature is verified
    using HS256. Otherwise falls back to unverified decode for development.

    Args:
        token: Supabase JWT token from Authorization header

    Returns:
        Decoded token payload with user info

    Raises:
        AuthenticationError: If token is invalid
    """
    try:
        jwt_secret = settings.SUPABASE_JWT_SECRET

        if jwt_secret:
            # Production: verify signature with the Supabase JWT secret
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        else:
            # Development fallback: decode without signature verification
            logger.warning("SUPABASE_JWT_SECRET not set — skipping signature verification")
            payload = jwt.decode(
                token,
                settings.SUPABASE_ANON_KEY,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_signature": False, "verify_aud": True},
            )

        # Validate token hasn't expired (belt-and-suspenders; jwt.decode checks too)
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise AuthenticationError("Token has expired")

        return payload

    except JWTError as e:
        logger.error(f"Supabase token verification failed: {e}")
        raise AuthenticationError("Invalid Supabase token")


def is_supabase_token(token: str) -> bool:
    """
    Heuristic to detect whether a token was issued by Supabase Auth.

    Supabase tokens contain an "iss" claim pointing to the project URL
    and an "aud" claim set to "authenticated".
    """
    try:
        # Peek at claims without verifying (just to route)
        unverified = jwt.get_unverified_claims(token)
        iss = unverified.get("iss", "")
        aud = unverified.get("aud", "")
        return "supabase" in iss or aud == "authenticated"
    except Exception:
        return False


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
