"""
Audit Log Model

Records admin actions for audit trail purposes.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    """
    Audit log model — tracks admin actions.

    Attributes:
        id: UUID primary key
        admin_id: Foreign key to the admin user who performed the action
        action: Action identifier (e.g. "user.created", "schedule.updated")
        target_type: Type of entity targeted (e.g. "user", "schedule")
        target_id: ID of the targeted entity (optional)
        details: Additional details (free text / JSON)
        created_at: When the action was performed
    """

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, admin_id={self.admin_id})>"
