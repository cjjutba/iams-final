"""
Settings Router

Admin-only endpoints for reading and updating system settings.
Changes persist in-memory until the process restarts.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.config import settings
from app.models.user import User
from app.utils.dependencies import get_current_admin

router = APIRouter()

# Fields exposed to the admin settings page
_EXPOSED_SETTINGS = [
    "RECOGNITION_THRESHOLD",
    "RECOGNITION_MARGIN",
    "QUALITY_BLUR_THRESHOLD",
    "EARLY_LEAVE_THRESHOLD",
    "GRACE_PERIOD_MINUTES",
    "SCAN_INTERVAL_SECONDS",
]


class SettingsUpdate(BaseModel):
    recognition_threshold: float | None = None
    recognition_margin: float | None = None
    quality_blur_threshold: float | None = None
    early_leave_threshold: int | None = None
    grace_period_minutes: int | None = None
    scan_interval_seconds: int | None = None


@router.get("/", status_code=status.HTTP_200_OK)
def get_settings(current_user: User = Depends(get_current_admin)):
    """Return current system settings (exposed subset)."""
    return {
        "success": True,
        "data": {
            "recognition_threshold": settings.RECOGNITION_THRESHOLD,
            "recognition_margin": settings.RECOGNITION_MARGIN,
            "quality_blur_threshold": settings.QUALITY_BLUR_THRESHOLD,
            "early_leave_threshold": settings.EARLY_LEAVE_THRESHOLD,
            "grace_period_minutes": settings.GRACE_PERIOD_MINUTES,
            "scan_interval_seconds": settings.SCAN_INTERVAL_SECONDS,
        },
    }


@router.patch("/", status_code=status.HTTP_200_OK)
def update_settings(
    updates: SettingsUpdate,
    current_user: User = Depends(get_current_admin),
):
    """
    Update system settings in-memory.
    Changes persist until the process restarts.
    """
    changed = {}
    for field_name, value in updates.model_dump(exclude_none=True).items():
        attr = field_name.upper()
        if attr in _EXPOSED_SETTINGS:
            setattr(settings, attr, value)
            changed[field_name] = value

    return {
        "success": True,
        "message": f"Updated {len(changed)} setting(s)",
        "data": changed,
    }
