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
    first_name: str
    last_name: str
    course: str
    year: int
    section: str
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
    phone: Optional[str] = None
    # first_name, last_name, etc. are pre-filled from verification


class RegisterResponse(BaseModel):
    """Registration response"""
    success: bool
    message: str
    user: UserResponse
    tokens: TokenResponse
