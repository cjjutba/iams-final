"""
Custom Exception Classes and Global Exception Handlers

Defines application-specific exceptions and FastAPI exception handlers.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.config import logger


# ===== Custom Exception Classes =====

class IAMSException(Exception):
    """Base exception for all IAMS-specific errors"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class AuthenticationError(IAMSException):
    """Raised when authentication fails (401)"""
    pass


class AuthorizationError(IAMSException):
    """Raised when user doesn't have permission (403)"""
    pass


class NotFoundError(IAMSException):
    """Raised when resource not found (404)"""
    pass


class ValidationError(IAMSException):
    """Raised when validation fails (400)"""
    pass


class DuplicateError(IAMSException):
    """Raised when trying to create duplicate resource (409)"""
    pass


class FaceRecognitionError(IAMSException):
    """Raised when face recognition fails"""
    pass


class DatabaseError(IAMSException):
    """Raised when database operation fails"""
    pass


# ===== Exception Handlers =====

async def iams_exception_handler(request: Request, exc: IAMSException):
    """
    Global exception handler for IAMS custom exceptions

    Maps exception types to HTTP status codes
    """
    status_code_map = {
        AuthenticationError: status.HTTP_401_UNAUTHORIZED,
        AuthorizationError: status.HTTP_403_FORBIDDEN,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ValidationError: status.HTTP_400_BAD_REQUEST,
        DuplicateError: status.HTTP_409_CONFLICT,
        FaceRecognitionError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        DatabaseError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Log the error
    logger.error(f"{exc.__class__.__name__}: {exc.message}")

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": exc.__class__.__name__,
                "message": exc.message
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler for Pydantic validation errors

    Returns formatted validation errors
    """
    logger.error(f"Validation error: {exc.errors()}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "ValidationError",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unexpected exceptions

    Logs the error and returns a generic error response
    """
    logger.exception(f"Unexpected error: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        }
    )
