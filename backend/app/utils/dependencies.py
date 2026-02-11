"""
FastAPI Dependencies

Dependency injection functions for authentication, database sessions,
and role-based access control.
"""

import uuid
from typing import List
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings, logger
from app.models.user import User, UserRole
from app.utils.security import (
    verify_token,
    extract_bearer_token,
    verify_supabase_token,
    is_supabase_token,
)
from app.utils.exceptions import AuthenticationError, AuthorizationError, NotFoundError


# HTTP Bearer token scheme
security = HTTPBearer()


# ===== Database Session Dependency =====

def get_database() -> Session:
    """
    Get database session dependency (alias for get_db)

    Usage:
        @app.get("/items/")
        def get_items(db: Session = Depends(get_database)):
            return db.query(Item).all()
    """
    return get_db()


# ===== Authentication Dependencies =====

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Supports dual authentication:
    - Supabase Auth tokens (detected via issuer / audience claims)
    - Custom JWT tokens (legacy / fallback)

    Enforces:
    - is_active must be True
    - email_verified must be True (when USE_SUPABASE_AUTH is enabled)

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Current user object

    Raises:
        HTTPException 401: If token is invalid or user not found
        HTTPException 403: If email is not verified or account inactive
    """
    token = credentials.credentials

    try:
        user_id = None

        # Route to the correct verifier based on token claims
        if is_supabase_token(token):
            payload = verify_supabase_token(token)
            user_id = payload.get("sub")
        else:
            try:
                payload = verify_token(token)
                user_id = payload.get("user_id")
            except AuthenticationError:
                # Custom JWT failed — try Supabase verification as fallback
                payload = verify_supabase_token(token)
                user_id = payload.get("sub")

        if not user_id:
            raise AuthenticationError("Invalid token: missing user identifier")

        # Fetch user from database (try by id first, then supabase_user_id)
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise AuthenticationError("Invalid user identifier format")

        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            user = db.query(User).filter(User.supabase_user_id == user_uuid).first()

        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        if not user.is_active:
            raise AuthorizationError("User account is inactive")

        # Enforce email verification when Supabase Auth is active
        if settings.USE_SUPABASE_AUTH and not user.email_verified:
            raise AuthorizationError("Email address has not been verified")

        return user

    except AuthorizationError as e:
        logger.warning(f"Authorization failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )
    except (AuthenticationError, NotFoundError) as e:
        logger.error(f"Authentication failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.exception(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (additional check for is_active)

    Args:
        current_user: Current user from get_current_user

    Returns:
        Current active user

    Raises:
        AuthenticationError: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


# ===== Role-Based Access Control =====

def require_role(*allowed_roles: UserRole):
    """
    Dependency factory for role-based access control

    Usage:
        @app.get("/admin/")
        def admin_only(user: User = Depends(require_role(UserRole.ADMIN))):
            return {"message": "Admin access granted"}

        @app.get("/faculty-or-admin/")
        def faculty_or_admin(user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN))):
            return {"message": "Faculty or admin access"}

    Args:
        *allowed_roles: Allowed user roles

    Returns:
        Dependency function that checks user role
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                f"Access denied for user {current_user.id} with role {current_user.role}. "
                f"Required roles: {allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join([r.value for r in allowed_roles])}"
            )
        return current_user

    return check_role


# ===== Specific Role Dependencies =====

async def get_current_student(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are a student

    Args:
        current_user: Current authenticated user

    Returns:
        Current student user

    Raises:
        AuthorizationError: If user is not a student
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to students"
        )
    return current_user


async def get_current_faculty(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are faculty

    Args:
        current_user: Current authenticated user

    Returns:
        Current faculty user

    Raises:
        AuthorizationError: If user is not faculty
    """
    if current_user.role != UserRole.FACULTY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to faculty"
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are admin

    Args:
        current_user: Current authenticated user

    Returns:
        Current admin user

    Raises:
        AuthorizationError: If user is not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to administrators"
        )
    return current_user


# ===== Optional Authentication =====

async def get_optional_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User | None:
    """
    Get current user if authenticated, None otherwise

    Useful for endpoints that have different behavior for authenticated vs anonymous users.

    Args:
        authorization: Authorization header (optional)
        db: Database session

    Returns:
        Current user if authenticated, None otherwise
    """
    if not authorization:
        return None

    try:
        token = extract_bearer_token(authorization)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await get_current_user(credentials, db)
    except Exception:
        return None
