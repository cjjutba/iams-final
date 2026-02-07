"""
Attendance Schemas

Request and response models for attendance tracking.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, date, time
from pydantic import BaseModel, Field, field_validator
from app.models.attendance_record import AttendanceStatus


class AttendanceRecordBase(BaseModel):
    """Shared attendance fields"""
    date: date
    status: AttendanceStatus
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    presence_score: float = Field(0.0, ge=0.0, le=100.0)
    remarks: Optional[str] = None


class ManualAttendanceRequest(BaseModel):
    """Manual attendance entry request (faculty override)"""
    student_id: str
    schedule_id: str
    date: date
    status: AttendanceStatus
    remarks: Optional[str] = None


class AttendanceRecordResponse(AttendanceRecordBase):
    """Full attendance record response"""
    id: str
    student_id: str
    schedule_id: str
    total_scans: int
    scans_present: int
    student_name: Optional[str] = None
    subject_code: Optional[str] = None

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
    scan_number: int
    scan_time: datetime
    detected: bool
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class EarlyLeaveResponse(BaseModel):
    """Early leave event"""
    id: str
    detected_at: datetime
    last_seen_at: datetime
    consecutive_misses: int
    notified: bool
    notified_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v):
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
    student_name: str
    status: AttendanceStatus
    check_in_time: Optional[datetime]
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
    students: List[StudentAttendanceStatus] = []
