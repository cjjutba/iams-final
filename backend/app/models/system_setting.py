"""
System Setting Model

Key-value store for system-wide configuration settings.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SystemSetting(Base):
    """
    System setting model

    Stores system-wide configuration as key-value pairs.

    Attributes:
        id: UUID primary key
        key: Unique setting key (e.g., 'scan_interval', 'max_retries')
        value: Setting value (stored as text)
        updated_by: Foreign key to admin who last updated the setting
        updated_at: When the setting was last updated
    """

    __tablename__ = "system_settings"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Setting data
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)

    # Metadata
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self):
        return f"<SystemSetting(key={self.key}, value={self.value})>"
