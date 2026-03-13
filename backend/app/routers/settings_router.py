"""
Settings Router

API endpoints for system-wide settings management (admin only).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.utils.dependencies import get_current_admin

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Request model for updating system settings"""

    settings: dict[str, str]


@router.get("/", status_code=status.HTTP_200_OK)
def get_settings(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Get System Settings** (Admin Only)

    Retrieve all system settings as key-value pairs.

    Requires admin authentication.
    """
    settings = db.query(SystemSetting).all()
    return {
        s.key: {
            "value": s.value,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in settings
    }


@router.patch("/", status_code=status.HTTP_200_OK)
def update_settings(
    data: SettingsUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Update System Settings** (Admin Only)

    Create or update system settings. Accepts a dictionary of key-value pairs.

    Requires admin authentication.
    """
    for key, value in data.settings.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = value
            setting.updated_by = current_user.id
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = SystemSetting(key=key, value=value, updated_by=current_user.id)
            db.add(setting)
    db.commit()
    return {"success": True, "message": "Settings updated"}
