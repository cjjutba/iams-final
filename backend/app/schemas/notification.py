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


# ===== Notification Preferences =====


class NotificationPreferenceResponse(BaseModel):
    """Notification preference response model"""

    early_leave_alerts: bool
    anomaly_alerts: bool
    attendance_confirmation: bool
    low_attendance_warning: bool
    daily_digest: bool
    weekly_digest: bool
    email_enabled: bool
    low_attendance_threshold: float

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    """Partial update model for notification preferences"""

    early_leave_alerts: bool | None = None
    anomaly_alerts: bool | None = None
    attendance_confirmation: bool | None = None
    low_attendance_warning: bool | None = None
    daily_digest: bool | None = None
    weekly_digest: bool | None = None
    email_enabled: bool | None = None
    low_attendance_threshold: float | None = None
