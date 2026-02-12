"""
Schedule Schemas

Request and response models for class schedules.
"""

from typing import Optional, List
from uuid import UUID
from datetime import time
from pydantic import BaseModel, Field, field_validator
from app.schemas.user import UserResponse


class ScheduleBase(BaseModel):
    """Shared schedule fields"""
    subject_code: str = Field(..., max_length=20)
    subject_name: str = Field(..., max_length=200)
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    semester: str = Field(..., max_length=20, description="e.g., '1st', '2nd', 'Summer'")
    academic_year: str = Field(..., max_length=20, description="e.g., '2024-2025'")
    target_course: Optional[str] = Field(None, max_length=100, description="Target course for auto-enrollment, e.g., 'BSCPE'")
    target_year_level: Optional[int] = Field(None, ge=1, le=6, description="Target year level for auto-enrollment, e.g., 4")


class ScheduleCreate(ScheduleBase):
    """Schedule creation request"""
    faculty_id: str
    room_id: str


class ScheduleUpdate(BaseModel):
    """Schedule update request (all fields optional)"""
    subject_code: Optional[str] = Field(None, max_length=20)
    subject_name: Optional[str] = Field(None, max_length=200)
    faculty_id: Optional[str] = None
    room_id: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    semester: Optional[str] = Field(None, max_length=20)
    academic_year: Optional[str] = Field(None, max_length=20)
    target_course: Optional[str] = Field(None, max_length=100)
    target_year_level: Optional[int] = Field(None, ge=1, le=6)
    is_active: Optional[bool] = None


class RoomInfo(BaseModel):
    """Room information"""
    id: str
    name: str
    building: str
    capacity: Optional[int]

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class ScheduleResponse(ScheduleBase):
    """Schedule response"""
    id: str
    faculty_id: str
    room_id: str
    is_active: bool
    faculty: Optional[UserResponse] = None
    room: Optional[RoomInfo] = None

    @field_validator("id", "faculty_id", "room_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class StudentInfo(BaseModel):
    """Student information for enrollment list"""
    id: str
    student_id: str
    first_name: str
    last_name: str
    email: str

    class Config:
        from_attributes = True


class ScheduleWithStudents(ScheduleResponse):
    """Schedule with enrolled students list"""
    enrolled_students: List[StudentInfo] = []
