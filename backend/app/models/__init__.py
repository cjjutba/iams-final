"""
Database Models Package

Exports all SQLAlchemy models for easy import.
"""

from app.database import Base
from app.models.user import User, UserRole
from app.models.face_registration import FaceRegistration
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.enrollment import Enrollment
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.presence_log import PresenceLog
from app.models.early_leave_event import EarlyLeaveEvent

__all__ = [
    "Base",
    "User",
    "UserRole",
    "FaceRegistration",
    "Room",
    "Schedule",
    "Enrollment",
    "AttendanceRecord",
    "AttendanceStatus",
    "PresenceLog",
    "EarlyLeaveEvent",
]
