"""
Face Recognition Schemas

Request and response models for face registration and recognition.
CRITICAL: Includes Edge API contract for Raspberry Pi integration.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ===== Face Registration (Mobile App) =====

class FaceRegisterResponse(BaseModel):
    """Face registration response"""
    success: bool
    message: str
    embedding_id: Optional[int] = None
    user_id: str


class FaceStatusResponse(BaseModel):
    """Face registration status"""
    registered: bool
    registered_at: Optional[datetime] = None
    embedding_id: Optional[int] = None


# ===== Edge API Contract (Raspberry Pi → Backend) =====

class FaceData(BaseModel):
    """
    Single face data from edge device

    CRITICAL: This is the contract between Raspberry Pi and backend.
    Do not change without updating edge code.
    """
    image: str = Field(
        ...,
        description="Base64-encoded JPEG image",
        min_length=1,  # Prevent empty strings
        max_length=15_000_000  # ~10MB Base64 encoded (prevents DoS)
    )
    bbox: Optional[List[int]] = Field(
        None,
        min_length=4,
        max_length=4,
        description="Bounding box [x, y, w, h]. Optional for MediaPipe compatibility."
    )

    @field_validator('bbox')
    @classmethod
    def validate_bbox(cls, v):
        """Validate bounding box values are reasonable"""
        if v is not None and len(v) == 4:
            if any(val < 0 for val in v):
                raise ValueError("bbox values must be non-negative")
            if v[2] <= 0 or v[3] <= 0:  # width and height
                raise ValueError("bbox width and height must be positive")
        return v


class EdgeProcessRequest(BaseModel):
    """
    Edge API request from Raspberry Pi

    CRITICAL: This is the primary interface for continuous presence tracking.
    """
    request_id: Optional[str] = Field(
        None,
        description="Idempotency key for retries. Prevents duplicate processing.",
        max_length=100
    )
    room_id: str = Field(
        ...,
        description="Room UUID or identifier",
        max_length=100,
        pattern=r'^[a-zA-Z0-9\-]+$'
    )
    timestamp: datetime = Field(..., description="Scan timestamp (ISO format)")
    faces: List[FaceData] = Field(
        ...,
        description="List of detected faces",
        min_length=1,
        max_length=10  # Limit batch size to prevent resource exhaustion
    )


class MatchedUser(BaseModel):
    """Matched user from face recognition"""
    user_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class EdgeProcessResponseData(BaseModel):
    """Processing results data"""
    processed: int = Field(..., description="Number of faces processed")
    matched: List[dict] = Field(..., description="Matched users with confidence")
    unmatched: int = Field(..., description="Number of unmatched faces")
    processing_time_ms: Optional[int] = Field(None, description="Total processing time in milliseconds")
    presence_logged: Optional[int] = Field(None, description="Number of presence logs created")


class EdgeProcessResponse(BaseModel):
    """
    Edge API response to Raspberry Pi

    Returns processing results including matched users and metrics.
    """
    success: bool
    data: Optional[EdgeProcessResponseData] = None
    error: Optional[dict] = Field(
        None,
        description="Error details if success=false",
        example={
            "code": "INVALID_IMAGE_FORMAT",
            "message": "Face 1: Invalid Base64 encoding",
            "retry": False
        }
    )


# ===== Face Recognition (Single Image) =====

class FaceRecognizeRequest(BaseModel):
    """Single face recognition request"""
    image: str = Field(..., description="Base64-encoded JPEG image")


class FaceRecognizeResponse(BaseModel):
    """Single face recognition response"""
    success: bool
    matched: bool
    user_id: Optional[str] = None
    confidence: Optional[float] = None
