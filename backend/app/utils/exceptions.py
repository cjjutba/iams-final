"""
Custom Exception Classes and Global Exception Handlers

Defines application-specific exceptions and FastAPI exception handlers.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import logger

# ===== Custom Exception Classes =====


class IAMSError(Exception):
    """Base exception for all IAMS-specific errors"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class AuthenticationError(IAMSError):
    """Raised when authentication fails (401)"""

    pass


class AuthorizationError(IAMSError):
    """Raised when user doesn't have permission (403)"""

    pass


class NotFoundError(IAMSError):
    """Raised when resource not found (404)"""

    pass


class ValidationError(IAMSError):
    """Raised when validation fails (400)"""

    pass


class DuplicateError(IAMSError):
    """Raised when trying to create duplicate resource (409)"""

    pass


class FaceRecognitionError(IAMSError):
    """Raised when face recognition fails"""

    pass


class DatabaseError(IAMSError):
    """Raised when database operation fails"""

    pass


class EdgeAPIError(IAMSError):
    """
    Raised when Edge API processing fails

    Includes error_code and retry flag for edge device retry logic.
    """

    def __init__(self, message: str, error_code: str, retry: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retry = retry


# ===== Exception Handlers =====


async def iams_exception_handler(request: Request, exc: IAMSError):
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
        EdgeAPIError: status.HTTP_200_OK,  # Edge API returns 200 with error details
    }

    status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Log the error
    logger.error(f"{exc.__class__.__name__}: {exc.message}")

    # Special handling for EdgeAPIError
    if isinstance(exc, EdgeAPIError):
        return JSONResponse(
            status_code=status_code,
            content={"success": False, "error": {"code": exc.error_code, "message": exc.message, "retry": exc.retry}},
        )

    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": exc.__class__.__name__, "message": exc.message}},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler for Pydantic validation errors

    Returns formatted validation errors
    """
    errors = exc.errors()
    logger.error(f"Validation error: {errors}")

    # Convert error context to JSON-serializable format
    serializable_errors = []
    for error in errors:
        error_dict = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "input": str(error.get("input")) if error.get("input") is not None else None,
        }
        # Skip ctx field as it may contain non-serializable objects
        serializable_errors.append(error_dict)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "ValidationError",
                "message": "Request validation failed",
                "details": serializable_errors,
            },
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unexpected exceptions

    Logs the error and returns a generic error response
    """
    logger.exception(f"Unexpected error: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "error": {"code": "InternalServerError", "message": "An unexpected error occurred"}},
    )
