"""
Database Models Package

Exports all SQLAlchemy models for easy import.
"""

from app.database import Base
from app.models.activity_event import ActivityEvent
from app.models.attendance_anomaly import AnomalyType, AttendanceAnomaly
from app.models.attendance_prediction import AttendancePrediction, RiskLevel
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.audit_log import AuditLog
from app.models.early_leave_event import EarlyLeaveEvent
from app.models.engagement_score import EngagementScore
from app.models.enrollment import Enrollment
from app.models.face_embedding import FaceEmbedding
from app.models.face_registration import FaceRegistration
from app.models.faculty_record import FacultyRecord
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.presence_log import PresenceLog
from app.models.recognition_access_audit import RecognitionAccessAudit
from app.models.recognition_event import RecognitionEvent
from app.models.refresh_token import RefreshToken
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.student_record import StudentRecord
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole

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
    "RecognitionAccessAudit",
    "RecognitionEvent",
    "RefreshToken",
    "EarlyLeaveEvent",
    "Notification",
    "StudentRecord",
    "FacultyRecord",
    "NotificationPreference",
    "SystemSetting",
    "AttendanceAnomaly",
    "AnomalyType",
    "EngagementScore",
    "AttendancePrediction",
    "RiskLevel",
    "AuditLog",
    "ActivityEvent",
]
