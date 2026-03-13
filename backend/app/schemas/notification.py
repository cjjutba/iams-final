"""
Notification Schemas

Request and response models for notification operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class NotificationResponse(BaseModel):
    """Notification response model"""

    id: str
    user_id: str
    title: str
    message: str
    type: str
    read: bool
    read_at: datetime | None = None
    reference_id: str | None = None
    reference_type: str | None = None
    created_at: datetime

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    """Internal schema for creating notifications"""

    user_id: str
    title: str
    message: str
    type: str = "system"
    reference_id: str | None = None
    reference_type: str | None = None
