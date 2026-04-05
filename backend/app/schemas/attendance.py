"""
Attendance Schemas

Request and response models for attendance tracking.
"""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.attendance_record import AttendanceStatus


class AttendanceRecordBase(BaseModel):
    """Shared attendance fields"""

    date: date
    status: AttendanceStatus
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    presence_score: float = Field(0.0, ge=0.0, le=100.0)
    remarks: str | None = None


class ManualAttendanceRequest(BaseModel):
    """Manual attendance entry request (faculty override)"""

    student_id: str
    schedule_id: str
    date: date
    status: AttendanceStatus
    remarks: str | None = None


class AttendanceRecordResponse(AttendanceRecordBase):
    """Full attendance record response"""

    id: str
    student_id: str
    schedule_id: str
    total_scans: int
    scans_present: int
    student_name: str | None = None
    subject_code: str | None = None

    @field_validator("id", "student_id", "schedule_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class PresenceLogResponse(BaseModel):
    """Individual presence scan log"""

    id: int
    attendance_id: str
    scan_number: int
    scan_time: datetime
    detected: bool
    confidence: float | None = None

    @field_validator("attendance_id", mode="before")
    @classmethod
    def coerce_attendance_id_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class EarlyLeaveResponse(BaseModel):
    """Early leave event"""

    id: str
    detected_at: datetime
    last_seen_at: datetime
    consecutive_misses: int
    notified: bool
    notified_at: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class EarlyLeaveEventResponse(BaseModel):
    """Early leave event with attendance ID"""

    id: str
    attendance_id: str
    detected_at: datetime
    last_seen_at: datetime
    consecutive_misses: int
    notified: bool
    notified_at: datetime | None = None

    @field_validator("id", "attendance_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class AttendanceSummary(BaseModel):
    """Attendance summary statistics"""

    total_classes: int
    present_count: int
    late_count: int
    absent_count: int
    early_leave_count: int
    attendance_rate: float = Field(..., ge=0.0, le=100.0)


class StudentAttendanceStatus(BaseModel):
    """Individual student's current attendance status"""

    student_id: str
    student_number: str | None = None  # School ID (e.g. "21-A-02177")
    student_name: str
    status: AttendanceStatus
    check_in_time: datetime | None
    presence_score: float
    total_scans: int
    scans_present: int


class LiveAttendanceResponse(BaseModel):
    """Real-time attendance status for a class session"""

    schedule_id: str
    subject_code: str
    subject_name: str
    date: date
    start_time: time
    end_time: time
    session_active: bool
    total_enrolled: int
    present_count: int
    late_count: int
    absent_count: int
    early_leave_count: int
    students: list[StudentAttendanceStatus] = []


class AttendanceUpdateRequest(BaseModel):
    """Request model for updating attendance record"""

    status: AttendanceStatus | None = None
    remarks: str | None = None


class ScheduleAttendanceSummaryItem(BaseModel):
    """Per-schedule attendance summary for the faculty dashboard"""

    schedule_id: str
    subject_code: str
    subject_name: str
    start_time: time
    end_time: time
    room_name: str | None = None
    session_active: bool = False
    total_enrolled: int = 0
    present_count: int = 0
    late_count: int = 0
    absent_count: int = 0
    attendance_rate: float = Field(0.0, ge=0.0, le=100.0)

    @field_validator("schedule_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v


class AlertResponse(BaseModel):
    """Early leave alert response for faculty dashboard"""

    id: str
    attendance_id: str
    student_id: str
    student_name: str
    student_student_id: str | None = None
    schedule_id: str
    subject_code: str
    subject_name: str
    detected_at: datetime
    last_seen_at: datetime
    consecutive_misses: int
    notified: bool
    date: date
    returned: bool = False
    returned_at: datetime | None = None
    absence_duration_seconds: int | None = None

    @field_validator("id", "attendance_id", "student_id", "schedule_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
