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
    severity: str = "info"
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
    # Admin-facing alert categories (Phase 1).
    camera_alerts: bool
    ml_health_alerts: bool
    security_alerts: bool
    audit_alerts: bool
    schedule_conflict_alerts: bool
    face_alerts: bool
    daily_health_summary: bool
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
    # Admin-facing alert categories (Phase 1).
    camera_alerts: bool | None = None
    ml_health_alerts: bool | None = None
    security_alerts: bool | None = None
    audit_alerts: bool | None = None
    schedule_conflict_alerts: bool | None = None
    face_alerts: bool | None = None
    daily_health_summary: bool | None = None
    daily_digest: bool | None = None
    weekly_digest: bool | None = None
    email_enabled: bool | None = None
    low_attendance_threshold: float | None = None
