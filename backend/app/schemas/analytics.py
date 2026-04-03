"""
Analytics Schemas

Pydantic models for faculty analytics dashboard endpoints.
"""

from pydantic import BaseModel


class ClassOverviewResponse(BaseModel):
    schedule_id: str
    subject_name: str
    subject_code: str | None = None
    day_of_week: int  # 0=Monday .. 6=Sunday
    start_time: str
    end_time: str
    average_attendance_rate: float
    total_sessions: int
    total_enrolled: int
    early_leave_count: int
    anomaly_count: int


class AtRiskStudentResponse(BaseModel):
    student_id: str
    student_name: str
    schedule_id: str
    subject_name: str
    subject_code: str | None = None
    attendance_rate: float
    risk_level: str
    sessions_missed: int
    sessions_total: int


class AnomalyItemResponse(BaseModel):
    id: str
    description: str
    severity: str
    detected_at: str
    subject_name: str | None = None
    resolved: bool = False
