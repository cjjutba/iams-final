"""
Database Models Package

Exports all SQLAlchemy models for easy import.
"""

from app.database import Base
from app.models.user import User, UserRole
from app.models.face_registration import FaceRegistration
from app.models.face_embedding import FaceEmbedding
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.enrollment import Enrollment
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.presence_log import PresenceLog
from app.models.early_leave_event import EarlyLeaveEvent
from app.models.notification import Notification
from app.models.student_record import StudentRecord
from app.models.faculty_record import FacultyRecord
from app.models.engagement_score import EngagementScore
from app.models.attendance_anomaly import AttendanceAnomaly, AnomalyType
from app.models.attendance_prediction import AttendancePrediction, RiskLevel

__all__ = [
    "Base",
    "User",
    "UserRole",
    "FaceRegistration",
    "FaceEmbedding",
    "Room",
    "Schedule",
    "Enrollment",
    "AttendanceRecord",
    "AttendanceStatus",
    "PresenceLog",
    "EarlyLeaveEvent",
    "Notification",
    "StudentRecord",
    "FacultyRecord",
    "EngagementScore",
    "AttendanceAnomaly",
    "AnomalyType",
    "AttendancePrediction",
    "RiskLevel",
]
