"""
User Schemas

Request and response models for user operations.
"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import UserRole


class UserBase(BaseModel):
    """Shared user fields"""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class UserCreate(UserBase):
    """User creation request"""
    password: str = Field(..., min_length=8)
    role: UserRole
    student_id: Optional[str] = Field(None, max_length=50)


class UserUpdate(BaseModel):
    """User update request (all fields optional)"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class PasswordChange(BaseModel):
    """Password change request"""
    old_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    """User response (public fields only)"""
    id: str
    role: UserRole
    student_id: Optional[str]
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
