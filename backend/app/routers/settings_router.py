"""
Settings Router

Admin-only endpoints for reading and updating system settings.
Changes persist in-memory until the process restarts.
"""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.utils.dependencies import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter()

# Settings whose change should trigger an extra ML-behavior alert in addition
# to the generic settings_changed notification. These directly affect
# detection / recognition behavior at the next pipeline restart.
_ML_BEHAVIOR_KEYS = {
    "RECOGNITION_THRESHOLD",
    "RECOGNITION_MARGIN",
    "INSIGHTFACE_DET_SIZE",
    "INSIGHTFACE_DET_THRESH",
}

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
async def update_settings(
    updates: SettingsUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Update system settings in-memory.
    Changes persist until the process restarts.
    """
    # Snapshot old values BEFORE applying the patch so we can build a
    # proper old→new diff for the notification path.
    patch_dict = updates.model_dump(exclude_none=True)
    old_snapshot: dict[str, object] = {}
    for field_name in patch_dict:
        attr = field_name.upper()
        if attr in _EXPOSED_SETTINGS:
            old_snapshot[attr] = getattr(settings, attr, None)

    changed: dict[str, object] = {}
    changes: dict[str, dict[str, object]] = {}
    for field_name, value in patch_dict.items():
        attr = field_name.upper()
        if attr in _EXPOSED_SETTINGS:
            old_val = old_snapshot.get(attr)
            setattr(settings, attr, value)
            changed[field_name] = value
            if old_val != value:
                changes[attr] = {"old": old_val, "new": value}

    if changed:
        try:
            from app.utils.audit import log_audit

            details = ", ".join(f"{k}={v}" for k, v in changed.items())
            log_audit(
                db,
                admin_id=current_user.id,
                action="update",
                target_type="settings",
                target_id=None,
                details=f"Changed: {details}",
                activity_summary=f"Settings updated: {details}",
                activity_payload={"changed": changed},
            )
        except Exception:
            pass

        # Emit a settings_changed notification to the OTHER admins so they
        # see the audit trail in their bell. Plus a special ML-behavior
        # alert when one of the recognition / detection knobs flipped.
        try:
            from app.services.notification_service import notify_admins

            actor_label = (
                getattr(current_user, "full_name", None)
                or getattr(current_user, "email", None)
                or "An admin"
            )

            for setting_key, change in changes.items():
                old_val = change.get("old")
                new_val = change.get("new")
                try:
                    await notify_admins(
                        db,
                        title=f"Settings changed: {setting_key}",
                        message=(
                            f"{actor_label} changed '{setting_key}' from "
                            f"'{old_val}' to '{new_val}'."
                        ),
                        notification_type="settings_changed",
                        severity="warn",
                        preference_key="audit_alerts",
                        send_email=True,
                        dedup_window_seconds=300,
                        reference_id=f"setting:{setting_key}:{current_user.id}",
                        reference_type="composite_key",
                        toast_type="warning",
                        exclude_user_id=str(current_user.id),
                    )
                except Exception:
                    logger.exception("Failed to notify admins of settings change")

                if setting_key in _ML_BEHAVIOR_KEYS:
                    try:
                        await notify_admins(
                            db,
                            title=f"ML behavior change: {setting_key}",
                            message=(
                                f"{setting_key} changed to {new_val}. "
                                f"Recognition behavior will adapt at next "
                                f"pipeline restart."
                            ),
                            notification_type="recognition_threshold_changed",
                            severity="warn",
                            preference_key="ml_health_alerts",
                            send_email=True,
                            # No dedup — these changes are rare and impactful;
                            # we want every flip surfaced separately.
                            dedup_window_seconds=0,
                            reference_id=f"ml_setting:{setting_key}",
                            reference_type="settings",
                            toast_type="warning",
                        )
                    except Exception:
                        logger.exception(
                            "Failed to notify admins of ML threshold change"
                        )
        except Exception:
            logger.exception("Settings change notification dispatch failed")

    return {
        "success": True,
        "message": f"Updated {len(changed)} setting(s)",
        "data": changed,
    }
