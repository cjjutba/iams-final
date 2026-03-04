"""
Analytics Schemas

Pydantic models for analytics API responses.
"""

from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel


class ClassOverview(BaseModel):
    """Overview statistics for a class/schedule."""
    schedule_id: str
    subject_code: str
    subject_name: str
    total_sessions: int
    average_attendance_rate: float
    total_enrolled: int
    early_leave_count: int
    anomaly_count: int


class StudentRanking(BaseModel):
    """Student ranking within a class."""
    student_id: str
    student_name: str
    student_number: Optional[str] = None
    attendance_rate: float
    sessions_attended: int
    sessions_total: int
    engagement_score: Optional[float] = None


class AtRiskStudent(BaseModel):
    """At-risk student summary."""
    student_id: str
    student_name: str
    student_number: Optional[str] = None
    schedule_id: str
    subject_code: str
    current_rate: float
    predicted_rate: Optional[float] = None
    risk_level: Optional[str] = None
    trend: Optional[str] = None


class HeatmapEntry(BaseModel):
    """Single entry in attendance heatmap."""
    date: date
    attendance_rate: float
    total_students: int
    present_count: int


class StudentDashboard(BaseModel):
    """Student self-dashboard data."""
    overall_rate: float
    classes_attended: int
    classes_total: int
    current_streak: int
    average_engagement: Optional[float] = None
    subjects: List[dict]


class SubjectBreakdown(BaseModel):
    """Per-subject attendance breakdown for a student."""
    schedule_id: str
    subject_code: str
    subject_name: str
    attendance_rate: float
    sessions_attended: int
    sessions_total: int
    engagement_avg: Optional[float] = None


class AnomalyListItem(BaseModel):
    """Anomaly item for list display."""
    id: str
    student_id: str
    student_name: Optional[str] = None
    anomaly_type: str
    severity: str
    description: str
    resolved: bool
    detected_at: datetime


class SystemMetrics(BaseModel):
    """System-wide metrics for admin dashboard."""
    total_students: int
    total_faculty: int
    total_schedules: int
    total_attendance_records: int
    average_attendance_rate: float
    total_anomalies: int
    unresolved_anomalies: int
    total_early_leaves: int
