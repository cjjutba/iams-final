"""
Audit Log Schemas

Request and response models for audit log operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class AuditLogResponse(BaseModel):
    """Audit log response model"""

    id: str
    admin_id: str
    action: str
    target_type: str
    target_id: str | None = None
    details: str | None = None
    created_at: datetime

    @field_validator("id", "admin_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
