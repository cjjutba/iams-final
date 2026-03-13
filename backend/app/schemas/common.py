"""
Common Schemas

Shared response formats used across the API.
"""

from typing import Any

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Standard success response"""

    success: bool = True
    message: str
    data: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response"""

    success: bool = False
    error: dict[str, Any]


class MessageResponse(BaseModel):
    """Simple message response"""

    message: str


class PaginatedResponse(BaseModel):
    """Paginated list response"""

    success: bool = True
    data: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
