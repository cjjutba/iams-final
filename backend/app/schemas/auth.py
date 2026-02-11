"""
Authentication Schemas

Request and response models for authentication flows.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Login request (email/student_id + password)"""
    identifier: str = Field(..., description="Email or Student ID")
    password: str


class TokenResponse(BaseModel):
    """Token response after successful login"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class VerifyStudentIDRequest(BaseModel):
    """Student ID verification request (Step 1 of registration)"""
    student_id: str = Field(..., min_length=1, max_length=50)


class StudentInfo(BaseModel):
    """Student information from university database"""
    student_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    course: Optional[str] = None
    year: Optional[int] = None
    section: Optional[str] = None
    email: Optional[str] = None


class VerifyStudentIDResponse(BaseModel):
    """Student ID verification response"""
    valid: bool
    student_info: Optional[StudentInfo] = None
    message: str


class RegisterRequest(BaseModel):
    """Student registration request (Step 2)"""
    student_id: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


class RegisterResponse(BaseModel):
    """Registration response"""
    success: bool
    message: str
    user: UserResponse
    tokens: Optional[TokenResponse] = None  # None when Supabase Auth is used (login via SDK)


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class ResendVerificationRequest(BaseModel):
    """Resend email verification request"""
    email: EmailStr


class ProfileUpdateRequest(BaseModel):
    """Profile update request (limited fields for self-service)"""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class SupabaseWebhookPayload(BaseModel):
    """Supabase Auth webhook payload"""
    type: str  # e.g. "user.updated"
    table: Optional[str] = None
    record: Optional[dict] = None
    old_record: Optional[dict] = None
