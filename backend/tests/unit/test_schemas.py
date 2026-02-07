"""
Unit Tests for Pydantic Schemas

Validates request/response schema parsing, field constraints, defaults,
and enum values. These tests run entirely in-memory with no I/O.
"""

from datetime import datetime, date, time

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    VerifyStudentIDRequest,
    VerifyStudentIDResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse
from app.schemas.face import (
    FaceData,
    EdgeProcessRequest,
    EdgeProcessResponse,
    MatchedUser,
    FaceRecognizeRequest,
    FaceRecognizeResponse,
)
from app.schemas.common import (
    SuccessResponse,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
)
from app.schemas.attendance import (
    AttendanceRecordBase,
    ManualAttendanceRequest,
    AttendanceSummary,
)
from app.models.attendance_record import AttendanceStatus
from app.models.user import UserRole


# ===================================================================
# LoginRequest
# ===================================================================


class TestLoginRequest:
    """Tests for LoginRequest schema."""

    def test_login_request_valid(self):
        """Valid identifier + password should parse without errors."""
        req = LoginRequest(identifier="student@test.edu", password="TestPass123")
        assert req.identifier == "student@test.edu"
        assert req.password == "TestPass123"

    def test_login_request_with_student_id(self):
        """Identifier can be a student ID string (not necessarily email)."""
        req = LoginRequest(identifier="STU-2024-001", password="TestPass123")
        assert req.identifier == "STU-2024-001"

    def test_login_request_missing_identifier(self):
        """Missing identifier should raise a validation error."""
        with pytest.raises(PydanticValidationError):
            LoginRequest(password="TestPass123")

    def test_login_request_missing_password(self):
        """Missing password should raise a validation error."""
        with pytest.raises(PydanticValidationError):
            LoginRequest(identifier="student@test.edu")


# ===================================================================
# RegisterRequest
# ===================================================================


class TestRegisterRequest:
    """Tests for RegisterRequest schema."""

    def test_register_request_valid(self):
        """All required fields present should parse correctly."""
        req = RegisterRequest(
            student_id="STU-2024-001",
            email="new@test.edu",
            password="StrongPass1",
            first_name="Juan",
            last_name="Dela Cruz",
        )
        assert req.student_id == "STU-2024-001"
        assert req.email == "new@test.edu"
        assert req.first_name == "Juan"
        assert req.phone is None  # optional, defaults to None

    def test_register_request_with_phone(self):
        """Optional phone field should be accepted."""
        req = RegisterRequest(
            student_id="STU-001",
            email="new@test.edu",
            password="StrongPass1",
            first_name="Juan",
            last_name="Dela Cruz",
            phone="09171234567",
        )
        assert req.phone == "09171234567"

    def test_register_request_missing_fields(self):
        """Omitting required fields should raise a validation error."""
        with pytest.raises(PydanticValidationError):
            RegisterRequest(student_id="STU-001")

    def test_register_request_invalid_email(self):
        """An invalid email format should raise a validation error."""
        with pytest.raises(PydanticValidationError):
            RegisterRequest(
                student_id="STU-001",
                email="not-an-email",
                password="StrongPass1",
                first_name="Juan",
                last_name="Dela Cruz",
            )

    def test_register_request_password_too_short(self):
        """Password shorter than 8 chars should fail Pydantic min_length."""
        with pytest.raises(PydanticValidationError):
            RegisterRequest(
                student_id="STU-001",
                email="new@test.edu",
                password="Short1",
                first_name="Juan",
                last_name="Dela Cruz",
            )

    def test_register_request_empty_first_name(self):
        """Empty first_name should fail min_length=1 constraint."""
        with pytest.raises(PydanticValidationError):
            RegisterRequest(
                student_id="STU-001",
                email="new@test.edu",
                password="StrongPass1",
                first_name="",
                last_name="Dela Cruz",
            )


# ===================================================================
# VerifyStudentIDRequest
# ===================================================================


class TestVerifyStudentIDRequest:
    """Tests for VerifyStudentIDRequest schema."""

    def test_verify_student_id_request_valid(self):
        """A non-empty student_id up to 50 chars should parse."""
        req = VerifyStudentIDRequest(student_id="STU-2024-001")
        assert req.student_id == "STU-2024-001"

    def test_verify_student_id_request_empty(self):
        """Empty student_id should fail min_length=1."""
        with pytest.raises(PydanticValidationError):
            VerifyStudentIDRequest(student_id="")

    def test_verify_student_id_request_too_long(self):
        """Student ID exceeding 50 characters should fail."""
        with pytest.raises(PydanticValidationError):
            VerifyStudentIDRequest(student_id="X" * 51)


# ===================================================================
# RefreshRequest
# ===================================================================


class TestRefreshRequest:
    """Tests for RefreshRequest schema."""

    def test_refresh_request_valid(self):
        req = RefreshRequest(refresh_token="some.jwt.token")
        assert req.refresh_token == "some.jwt.token"

    def test_refresh_request_missing_token(self):
        with pytest.raises(PydanticValidationError):
            RefreshRequest()


# ===================================================================
# AttendanceStatus Enum
# ===================================================================


class TestAttendanceStatusEnum:
    """Tests for the AttendanceStatus enum."""

    def test_attendance_status_values(self):
        """All four expected status values should exist."""
        assert AttendanceStatus.PRESENT.value == "present"
        assert AttendanceStatus.LATE.value == "late"
        assert AttendanceStatus.ABSENT.value == "absent"
        assert AttendanceStatus.EARLY_LEAVE.value == "early_leave"

    def test_attendance_status_from_string(self):
        """Should be constructable from its string value."""
        assert AttendanceStatus("present") == AttendanceStatus.PRESENT
        assert AttendanceStatus("early_leave") == AttendanceStatus.EARLY_LEAVE

    def test_attendance_status_invalid_value(self):
        """An invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            AttendanceStatus("unknown_status")

    def test_attendance_status_is_str_subclass(self):
        """AttendanceStatus should be usable as a plain string."""
        assert isinstance(AttendanceStatus.PRESENT, str)
        assert AttendanceStatus.PRESENT == "present"


# ===================================================================
# UserRole Enum
# ===================================================================


class TestUserRoleEnum:
    """Tests for the UserRole enum."""

    def test_user_role_values(self):
        assert UserRole.STUDENT.value == "student"
        assert UserRole.FACULTY.value == "faculty"
        assert UserRole.ADMIN.value == "admin"

    def test_user_role_from_string(self):
        assert UserRole("student") == UserRole.STUDENT

    def test_user_role_is_str_subclass(self):
        assert isinstance(UserRole.STUDENT, str)


# ===================================================================
# EdgeProcessRequest (RPi -> Backend contract)
# ===================================================================


class TestEdgeProcessRequest:
    """Tests for the critical Edge API request schema."""

    def test_edge_process_request_valid(self):
        """A well-formed request with one face should parse."""
        req = EdgeProcessRequest(
            room_id="room-uuid-123",
            timestamp=datetime(2025, 1, 15, 8, 30, 0),
            faces=[
                FaceData(
                    image="base64encodedimage==",
                    bbox=[100, 200, 50, 60],
                )
            ],
        )
        assert req.room_id == "room-uuid-123"
        assert len(req.faces) == 1
        assert req.faces[0].bbox == [100, 200, 50, 60]

    def test_edge_process_request_multiple_faces(self):
        """Multiple faces should be accepted."""
        req = EdgeProcessRequest(
            room_id="room-uuid-123",
            timestamp=datetime.utcnow(),
            faces=[
                FaceData(image="img1==", bbox=[0, 0, 10, 10]),
                FaceData(image="img2==", bbox=[20, 20, 30, 30]),
                FaceData(image="img3==", bbox=[40, 40, 50, 50]),
            ],
        )
        assert len(req.faces) == 3

    def test_edge_process_request_empty_faces_rejected(self):
        """
        An empty faces list should be rejected by schema validation.

        Empty faces arrays are now rejected at the schema level (min_length=1)
        to prevent unnecessary processing. The RPi should only send requests
        when it actually detects faces.
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            EdgeProcessRequest(
                room_id="room-uuid-123",
                timestamp=datetime.utcnow(),
                faces=[],
            )

        # Verify the error is about list length
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]['type'] == 'too_short'
        assert errors[0]['loc'] == ('faces',)

    def test_edge_process_request_missing_room_id(self):
        """Missing room_id should fail validation."""
        with pytest.raises(PydanticValidationError):
            EdgeProcessRequest(
                timestamp=datetime.utcnow(),
                faces=[],
            )

    def test_edge_process_request_missing_timestamp(self):
        """Missing timestamp should fail validation."""
        with pytest.raises(PydanticValidationError):
            EdgeProcessRequest(
                room_id="room-uuid-123",
                faces=[],
            )

    def test_face_data_bbox_wrong_length(self):
        """Bounding box must have exactly 4 elements."""
        with pytest.raises(PydanticValidationError):
            FaceData(image="base64==", bbox=[100, 200, 50])


# ===================================================================
# MatchedUser
# ===================================================================


class TestMatchedUser:
    """Tests for the MatchedUser schema."""

    def test_matched_user_valid(self):
        mu = MatchedUser(user_id="uuid-123", confidence=0.85)
        assert mu.confidence == 0.85

    def test_matched_user_confidence_too_high(self):
        """Confidence > 1.0 should fail ge/le constraint."""
        with pytest.raises(PydanticValidationError):
            MatchedUser(user_id="uuid-123", confidence=1.5)

    def test_matched_user_confidence_too_low(self):
        """Confidence < 0.0 should fail ge/le constraint."""
        with pytest.raises(PydanticValidationError):
            MatchedUser(user_id="uuid-123", confidence=-0.1)

    def test_matched_user_boundary_values(self):
        """Confidence at 0.0 and 1.0 should be accepted."""
        assert MatchedUser(user_id="a", confidence=0.0).confidence == 0.0
        assert MatchedUser(user_id="a", confidence=1.0).confidence == 1.0


# ===================================================================
# Common Schemas
# ===================================================================


class TestCommonSchemas:
    """Tests for SuccessResponse, ErrorResponse, MessageResponse, PaginatedResponse."""

    def test_success_response_defaults(self):
        resp = SuccessResponse(message="Done")
        assert resp.success is True
        assert resp.data is None

    def test_success_response_with_data(self):
        resp = SuccessResponse(message="Done", data={"count": 5})
        assert resp.data["count"] == 5

    def test_error_response(self):
        resp = ErrorResponse(error={"code": "NotFound", "message": "Item not found"})
        assert resp.success is False
        assert resp.error["code"] == "NotFound"

    def test_message_response(self):
        resp = MessageResponse(message="Hello")
        assert resp.message == "Hello"

    def test_paginated_response(self):
        resp = PaginatedResponse(
            data=[1, 2, 3],
            total=10,
            page=1,
            page_size=3,
            total_pages=4,
        )
        assert resp.success is True
        assert len(resp.data) == 3
        assert resp.total_pages == 4


# ===================================================================
# AttendanceSummary
# ===================================================================


class TestAttendanceSummary:
    """Tests for AttendanceSummary schema."""

    def test_attendance_summary_valid(self):
        summary = AttendanceSummary(
            total_classes=20,
            present_count=15,
            late_count=3,
            absent_count=1,
            early_leave_count=1,
            attendance_rate=75.0,
        )
        assert summary.attendance_rate == 75.0

    def test_attendance_summary_rate_out_of_range(self):
        """attendance_rate must be between 0 and 100."""
        with pytest.raises(PydanticValidationError):
            AttendanceSummary(
                total_classes=20,
                present_count=15,
                late_count=3,
                absent_count=1,
                early_leave_count=1,
                attendance_rate=101.0,
            )

    def test_attendance_summary_rate_negative(self):
        with pytest.raises(PydanticValidationError):
            AttendanceSummary(
                total_classes=20,
                present_count=15,
                late_count=3,
                absent_count=1,
                early_leave_count=1,
                attendance_rate=-1.0,
            )


# ===================================================================
# UserCreate Schema
# ===================================================================


class TestUserCreateSchema:
    """Tests for UserCreate schema."""

    def test_user_create_valid_student(self):
        user = UserCreate(
            email="new@test.edu",
            first_name="Juan",
            last_name="Dela Cruz",
            password="StrongPass1",
            role=UserRole.STUDENT,
            student_id="STU-001",
        )
        assert user.role == UserRole.STUDENT
        assert user.student_id == "STU-001"

    def test_user_create_valid_faculty(self):
        user = UserCreate(
            email="faculty@test.edu",
            first_name="Maria",
            last_name="Santos",
            password="StrongPass1",
            role=UserRole.FACULTY,
        )
        assert user.role == UserRole.FACULTY
        assert user.student_id is None

    def test_user_create_missing_role(self):
        with pytest.raises(PydanticValidationError):
            UserCreate(
                email="test@test.edu",
                first_name="Test",
                last_name="User",
                password="StrongPass1",
            )

    def test_user_create_invalid_role(self):
        with pytest.raises(PydanticValidationError):
            UserCreate(
                email="test@test.edu",
                first_name="Test",
                last_name="User",
                password="StrongPass1",
                role="superadmin",
            )


# ===================================================================
# FaceRecognizeRequest / FaceRecognizeResponse
# ===================================================================


class TestFaceRecognizeSchemas:
    """Tests for single-image face recognition schemas."""

    def test_face_recognize_request_valid(self):
        req = FaceRecognizeRequest(image="base64data==")
        assert req.image == "base64data=="

    def test_face_recognize_request_missing_image(self):
        with pytest.raises(PydanticValidationError):
            FaceRecognizeRequest()

    def test_face_recognize_response_matched(self):
        resp = FaceRecognizeResponse(
            success=True, matched=True, user_id="uuid-123", confidence=0.92
        )
        assert resp.matched is True
        assert resp.confidence == 0.92

    def test_face_recognize_response_not_matched(self):
        resp = FaceRecognizeResponse(success=True, matched=False)
        assert resp.matched is False
        assert resp.user_id is None
        assert resp.confidence is None
