"""
Authentication Schemas

Request and response models for authentication flows.
"""

from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserResponse, _validate_ph_phone


class LoginRequest(BaseModel):
    """Login request (email/student_id + password)"""

    identifier: str = Field(..., description="Email or Student ID")
    password: str


class TokenResponse(BaseModel):
    """Token response after successful login"""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str


class CheckStudentIDRequest(BaseModel):
    """Check student ID availability (Step 1a of registration)"""

    student_id: str = Field(..., min_length=1, max_length=50)


class CheckStudentIDResponse(BaseModel):
    """Check student ID response"""

    exists: bool
    available: bool
    message: str


class VerifyStudentIDRequest(BaseModel):
    """Student ID verification request (Step 1 of registration)"""

    student_id: str = Field(..., min_length=1, max_length=50)
    birthdate: date = Field(..., description="Birthdate for identity verification (YYYY-MM-DD)")


class StudentInfo(BaseModel):
    """Student information from university database"""

    student_id: str
    first_name: str | None = None
    last_name: str | None = None
    course: str | None = None
    year: int | None = None
    section: str | None = None
    email: str | None = None
    contact_number: str | None = None


class VerifyStudentIDResponse(BaseModel):
    """Student ID verification response"""

    valid: bool
    student_info: StudentInfo | None = None
    message: str


class RegisterRequest(BaseModel):
    """Student registration request (Step 2)"""

    student_id: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=11)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v):
        return _validate_ph_phone(v)


class RegisterResponse(BaseModel):
    """Registration response"""

    success: bool
    message: str
    user: UserResponse
    tokens: TokenResponse | None = None


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""

    email: EmailStr


class ProfileUpdateRequest(BaseModel):
    """Profile update request (limited fields for self-service)"""

    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=11)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v):
        return _validate_ph_phone(v)

