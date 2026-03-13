"""
Audit Log Model

Tracks administrative actions for accountability and compliance.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AuditLog(Base):
    """
    Audit log model

    Records admin actions for audit trail purposes.

    Attributes:
        id: UUID primary key
        admin_id: Foreign key to admin user who performed the action
        action: Action performed (e.g., 'create', 'update', 'delete')
        target_type: Type of entity acted upon (e.g., 'room', 'user')
        target_id: ID of the target entity
        details: Additional details about the action
        created_at: When the action occurred
    """

    __tablename__ = "audit_logs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who performed the action
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # What was done
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)

    # When
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, target_type={self.target_type})>"
