"""
Notification Model

Represents in-app notifications for users (attendance alerts, system messages, etc.).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Notification(Base):
    """
    Notification model

    Represents an in-app notification sent to a user.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to recipient user
        title: Notification title
        message: Notification body text
        type: Notification category (attendance, alert, system, etc.)
        read: Whether the notification has been read
        read_at: When the notification was read
        reference_id: Optional reference to related entity (e.g., attendance_id)
        reference_type: Type of referenced entity (e.g., "attendance", "early_leave")
        created_at: When the notification was created
    """

    __tablename__ = "notifications"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Recipient
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False, default="system", index=True)

    # Read status
    read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)

    # Optional reference to related entity
    reference_id = Column(String(255), nullable=True)
    reference_type = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="notifications")

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type}, read={self.read})>"
