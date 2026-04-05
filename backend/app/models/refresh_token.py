"""
Refresh Token Model

Stores hashed refresh tokens for secure token rotation and revocation.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class RefreshToken(Base):
    """
    Refresh token model for JWT token management.

    Each row represents a single issued refresh token.
    Tokens are stored as hashes so that a database leak does not
    directly expose valid tokens.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to users table
        token_hash: SHA-256 hash of the raw refresh token
        expires_at: When the token expires
        revoked: Whether the token has been explicitly revoked
        created_at: When the token was issued
    """

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"
