"""
User Schemas

Request and response models for user operations.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole

PH_PHONE_PATTERN = re.compile(r"^09\d{9}$")


def _validate_ph_phone(v: str | None) -> str | None:
    """Validate PH phone number: exactly 11 digits starting with 09."""
    if v is None or v == "":
        return None
    digits = re.sub(r"\D", "", v)
    if not PH_PHONE_PATTERN.match(digits):
        raise ValueError("Phone number must be exactly 11 digits starting with 09 (e.g. 09xxxxxxxxx)")
    return digits


class UserBase(BaseModel):
    """Shared user fields"""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=11)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v):
        return _validate_ph_phone(v)


class UserCreate(UserBase):
    """User creation request"""

    password: str = Field(..., min_length=8)
    role: UserRole
    student_id: str | None = Field(None, max_length=50)


class AdminCreateUser(BaseModel):
    """Admin-initiated user creation request"""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=11)
    password: str = Field(..., min_length=8)
    role: UserRole

    # Student-specific fields
    student_id: str | None = Field(None, max_length=50)
    course: str | None = Field(None, max_length=100)
    year_level: int | None = Field(None, ge=1, le=5)
    section: str | None = Field(None, max_length=10)
    birthdate: str | None = Field(None)  # ISO date string YYYY-MM-DD
    contact_number: str | None = Field(None, max_length=11)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v):
        return _validate_ph_phone(v)

    @field_validator("contact_number", mode="before")
    @classmethod
    def validate_contact_number(cls, v):
        return _validate_ph_phone(v)


class CreateStudentRecord(BaseModel):
    """Admin-initiated student record creation (no auth account)"""

    student_id: str = Field(..., min_length=1, max_length=50)
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr | None = None
    course: str | None = Field(None, max_length=100)
    year_level: int | None = Field(None, ge=1, le=5)
    section: str | None = Field(None, max_length=10)
    birthdate: str | None = Field(None)  # ISO date string YYYY-MM-DD
    contact_number: str | None = Field(None, max_length=11)

    @field_validator("contact_number", mode="before")
    @classmethod
    def validate_contact_number(cls, v):
        return _validate_ph_phone(v)


class StudentRecordResponse(BaseModel):
    """Student record response"""

    student_id: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    email: str | None = None
    course: str | None = None
    year_level: int | None = None
    section: str | None = None
    birthdate: str | None = None
    contact_number: str | None = None
    is_active: bool
    created_at: datetime

    @field_validator("birthdate", mode="before")
    @classmethod
    def coerce_date_to_str(cls, v):
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    class Config:
        from_attributes = True


class StudentRecordWithStatusResponse(StudentRecordResponse):
    """Student record with app registration status"""

    user_id: str | None = None
    is_registered: bool = False
    has_face_registered: bool = False


class UpdateStudentRecord(BaseModel):
    """Update student record request (all fields optional)"""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    course: str | None = Field(None, max_length=100)
    year_level: int | None = Field(None, ge=1, le=5)
    section: str | None = Field(None, max_length=10)
    birthdate: str | None = Field(None)
    contact_number: str | None = Field(None, max_length=11)

    @field_validator("contact_number", mode="before")
    @classmethod
    def validate_contact_number(cls, v):
        return _validate_ph_phone(v)


class UserUpdate(BaseModel):
    """User update request (all fields optional)"""

    email: EmailStr | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=11)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v):
        return _validate_ph_phone(v)


class PasswordChange(BaseModel):
    """Password change request"""

    old_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    """User response (public fields only)"""

    id: str
    role: UserRole
    student_id: str | None
    is_active: bool
    email_verified: bool = False
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """User with password hash (internal use only)"""

    password_hash: str
