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

# Cached JWKS keys from Supabase (fetched once, refreshed on kid miss)
_jwks_cache: Dict = {}
_jwks_cache_time: float = 0


def _fetch_supabase_jwks() -> Dict:
    """Fetch and cache the Supabase JWKS public keys."""
    import time
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    # Return cached keys if fresh (cache for 1 hour)
    if _jwks_cache and (now - _jwks_cache_time) < 3600:
        return _jwks_cache

    try:
        import httpx
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
            headers={"apikey": settings.SUPABASE_ANON_KEY},
            timeout=10.0,
        )
        if resp.status_code == 200:
            jwks = resp.json()
            # Index by kid for quick lookup
            _jwks_cache = {k["kid"]: k for k in jwks.get("keys", [])}
            _jwks_cache_time = now
            logger.debug(f"Fetched JWKS: {len(_jwks_cache)} key(s)")
            return _jwks_cache
    except Exception as e:
        logger.warning(f"Failed to fetch JWKS: {e}")

    return _jwks_cache  # Return stale cache on failure


def verify_supabase_token(token: str) -> Dict:
    """
    Verify a Supabase Auth JWT token.

    Supports both:
    - ES256 (asymmetric, JWKS) — current Supabase default
    - HS256 (symmetric, JWT secret) — legacy Supabase projects

    Args:
        token: Supabase JWT token from Authorization header

    Returns:
        Decoded token payload with user info

    Raises:
        AuthenticationError: If token is invalid
    """
    try:
        # Peek at the token header to determine algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        kid = header.get("kid")

        if alg == "ES256" and kid:
            # Asymmetric (JWKS) — fetch public key from Supabase
            jwks = _fetch_supabase_jwks()
            jwk = jwks.get(kid)
            if not jwk:
                # Key not in cache — force refresh and retry
                global _jwks_cache_time
                _jwks_cache_time = 0
                jwks = _fetch_supabase_jwks()
                jwk = jwks.get(kid)
            if not jwk:
                raise AuthenticationError(f"Unknown signing key: {kid}")

            payload = jwt.decode(
                token,
                jwk,
                algorithms=["ES256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        elif alg in ("HS256", "HS384", "HS512"):
            # Symmetric (HMAC) — use JWT secret
            jwt_secret = settings.SUPABASE_JWT_SECRET
            if not jwt_secret:
                logger.warning("SUPABASE_JWT_SECRET not set — skipping signature verification")
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_ANON_KEY,
                    algorithms=[alg],
                    audience="authenticated",
                    options={"verify_signature": False, "verify_aud": True},
                )
            else:
                payload = jwt.decode(
                    token,
                    jwt_secret,
                    algorithms=[alg],
                    audience="authenticated",
                    options={"verify_aud": True},
                )
        else:
            raise AuthenticationError(f"Unsupported JWT algorithm: {alg}")

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
