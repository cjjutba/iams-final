"""
Common Schemas

Shared response formats used across the API.
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: Dict[str, Any]


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str


class PaginatedResponse(BaseModel):
    """Paginated list response"""
    success: bool = True
    data: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
