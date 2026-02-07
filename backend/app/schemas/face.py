"""
Face Recognition Schemas

Request and response models for face registration and recognition.
CRITICAL: Includes Edge API contract for Raspberry Pi integration.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


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
    image: str = Field(..., description="Base64-encoded JPEG image")
    bbox: List[int] = Field(..., min_items=4, max_items=4, description="Bounding box [x, y, w, h]")


class EdgeProcessRequest(BaseModel):
    """
    Edge API request from Raspberry Pi

    CRITICAL: This is the primary interface for continuous presence tracking.
    """
    room_id: str = Field(..., description="Room UUID or identifier")
    timestamp: datetime = Field(..., description="Scan timestamp (ISO format)")
    faces: List[FaceData] = Field(..., description="List of detected faces")


class MatchedUser(BaseModel):
    """Matched user from face recognition"""
    user_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class EdgeProcessResponse(BaseModel):
    """
    Edge API response to Raspberry Pi

    Returns processing results including matched users.
    """
    success: bool
    data: dict = Field(
        ...,
        description="Processing results",
        example={
            "processed": 3,
            "matched": [
                {"user_id": "uuid", "confidence": 0.85}
            ],
            "unmatched": 1
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
