"""
Schemas Package

Exports all Pydantic schemas for request/response validation.
"""

from app.schemas.attendance import (
    AlertResponse,
    AttendanceRecordBase,
    AttendanceRecordResponse,
    AttendanceSummary,
    AttendanceUpdateRequest,
    EarlyLeaveResponse,
    LiveAttendanceResponse,
    ManualAttendanceRequest,
    PresenceLogResponse,
    StudentAttendanceStatus,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    StudentInfo,
    TokenResponse,
    VerifyStudentIDRequest,
    VerifyStudentIDResponse,
)
from app.schemas.common import ErrorResponse, MessageResponse, PaginatedResponse, SuccessResponse
from app.schemas.face import (
    EdgeProcessRequest,
    EdgeProcessResponse,
    FaceData,
    FaceRecognizeRequest,
    FaceRecognizeResponse,
    FaceRegisterResponse,
    FaceStatusResponse,
    MatchedUser,
)
from app.schemas.notification import NotificationCreate, NotificationResponse
from app.schemas.schedule import (
    RoomInfo,
    ScheduleBase,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    ScheduleWithStudents,
)
from app.schemas.schedule import (
    StudentInfo as ScheduleStudentInfo,
)
from app.schemas.user import PasswordChange, UserBase, UserCreate, UserInDB, UserResponse, UserUpdate

__all__ = [
    # Common
    "SuccessResponse",
    "ErrorResponse",
    "MessageResponse",
    "PaginatedResponse",
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "PasswordChange",
    "UserResponse",
    "UserInDB",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "VerifyStudentIDRequest",
    "StudentInfo",
    "VerifyStudentIDResponse",
    "RegisterRequest",
    "RegisterResponse",
    "ForgotPasswordRequest",
    "ProfileUpdateRequest",
    # Face
    "FaceData",
    "EdgeProcessRequest",
    "EdgeProcessResponse",
    "MatchedUser",
    "FaceRegisterResponse",
    "FaceStatusResponse",
    "FaceRecognizeRequest",
    "FaceRecognizeResponse",
    # Schedule
    "ScheduleBase",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    "ScheduleWithStudents",
    "RoomInfo",
    "ScheduleStudentInfo",
    # Attendance
    "AttendanceRecordBase",
    "ManualAttendanceRequest",
    "AttendanceRecordResponse",
    "AttendanceUpdateRequest",
    "PresenceLogResponse",
    "EarlyLeaveResponse",
    "AlertResponse",
    "AttendanceSummary",
    "StudentAttendanceStatus",
    "LiveAttendanceResponse",
    # Notification
    "NotificationResponse",
    "NotificationCreate",
]
