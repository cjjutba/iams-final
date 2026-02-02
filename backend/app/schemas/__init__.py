"""
Schemas Package

Exports all Pydantic schemas for request/response validation.
"""

from app.schemas.common import (
    SuccessResponse,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse
)

from app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    PasswordChange,
    UserResponse,
    UserInDB
)

from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    VerifyStudentIDRequest,
    StudentInfo,
    VerifyStudentIDResponse,
    RegisterRequest,
    RegisterResponse
)

from app.schemas.face import (
    FaceData,
    EdgeProcessRequest,
    EdgeProcessResponse,
    MatchedUser,
    FaceRegisterResponse,
    FaceStatusResponse,
    FaceRecognizeRequest,
    FaceRecognizeResponse
)

from app.schemas.schedule import (
    ScheduleBase,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleWithStudents,
    RoomInfo,
    StudentInfo
)

from app.schemas.attendance import (
    AttendanceRecordBase,
    ManualAttendanceRequest,
    AttendanceRecordResponse,
    PresenceLogResponse,
    EarlyLeaveResponse,
    AttendanceSummary,
    StudentAttendanceStatus,
    LiveAttendanceResponse
)

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
    # Attendance
    "AttendanceRecordBase",
    "ManualAttendanceRequest",
    "AttendanceRecordResponse",
    "PresenceLogResponse",
    "EarlyLeaveResponse",
    "AttendanceSummary",
    "StudentAttendanceStatus",
    "LiveAttendanceResponse",
]
