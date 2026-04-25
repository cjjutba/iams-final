"""
Schedule Schemas

Request and response models for class schedules.
"""

from datetime import time
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_validator

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
    target_course: str | None = Field(
        None, max_length=100, description="Target course for auto-enrollment, e.g., 'BSCPE'"
    )
    target_year_level: int | None = Field(
        None, ge=0, le=6, description="Target year level for auto-enrollment (0=any), e.g., 4"
    )
    early_leave_timeout_minutes: int | None = Field(
        None, ge=1, le=15, description="Early leave timeout in minutes (1-15). NULL = system default (5 min)."
    )


class ScheduleCreate(ScheduleBase):
    """Schedule creation request"""

    faculty_id: str
    room_id: str


class ScheduleUpdate(BaseModel):
    """Schedule update request (all fields optional)"""

    subject_code: str | None = Field(None, max_length=20)
    subject_name: str | None = Field(None, max_length=200)
    faculty_id: str | None = None
    room_id: str | None = None
    day_of_week: int | None = Field(None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    semester: str | None = Field(None, max_length=20)
    academic_year: str | None = Field(None, max_length=20)
    target_course: str | None = Field(None, max_length=100)
    target_year_level: int | None = Field(None, ge=0, le=6)
    early_leave_timeout_minutes: int | None = Field(None, ge=1, le=15)
    is_active: bool | None = None


class RoomInfo(BaseModel):
    """Room information"""

    id: str
    name: str
    building: str
    capacity: int | None

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
    faculty: UserResponse | None = None
    room: RoomInfo | None = None
    # Derived presentation status — distinct from `is_active` (which is the
    # enable/archive flag). Computed in the router from session_manager + the
    # current clock, defaulting to "scheduled" when ScheduleResponse is built
    # from an ORM row alone (e.g. in non-list contexts where the runtime
    # context isn't available). Possible values: "live", "upcoming",
    # "ended", "scheduled", "disabled". The admin Schedules list reads this
    # to render an honest status badge instead of always showing "Active".
    runtime_status: str = "scheduled"

    @computed_field
    @property
    def room_name(self) -> str | None:
        """Flat room name for mobile clients."""
        return self.room.name if self.room else None

    @computed_field
    @property
    def faculty_name(self) -> str | None:
        """Flat faculty display name for mobile clients."""
        if self.faculty:
            return f"{self.faculty.first_name} {self.faculty.last_name}"
        return None

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

    enrolled_students: list[StudentInfo] = []


class ScheduleConfigUpdate(BaseModel):
    """Faculty-facing config update for a schedule (subset of fields)."""

    early_leave_timeout_minutes: int = Field(..., ge=1, le=15)
