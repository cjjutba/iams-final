"""
Room Schemas

Request and response models for room operations.
"""

from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    """Room creation request"""

    name: str = Field(..., min_length=1, max_length=100)
    building: str = Field(..., min_length=1, max_length=100)
    capacity: int | None = None
    camera_endpoint: str | None = Field(None, max_length=255)


class RoomUpdate(BaseModel):
    """Room update request (all fields optional)"""

    name: str | None = Field(None, min_length=1, max_length=100)
    building: str | None = Field(None, min_length=1, max_length=100)
    capacity: int | None = None
    camera_endpoint: str | None = Field(None, max_length=255)
    is_active: bool | None = None
