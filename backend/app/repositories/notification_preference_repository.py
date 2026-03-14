"""
Notification Preference Repository

Data access layer for NotificationPreference operations.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference


class NotificationPreferenceRepository:
    """Repository for NotificationPreference CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: str) -> NotificationPreference | None:
        """Get preferences for a user, or None if not set."""
        return (
            self.db.query(NotificationPreference).filter(NotificationPreference.user_id == uuid.UUID(user_id)).first()
        )

    def get_or_create(self, user_id: str) -> NotificationPreference:
        """Get existing preferences or create defaults."""
        pref = self.get_by_user(user_id)
        if pref:
            return pref

        pref = NotificationPreference(user_id=uuid.UUID(user_id))
        self.db.add(pref)
        self.db.commit()
        self.db.refresh(pref)
        return pref

    def update(self, user_id: str, updates: dict[str, Any]) -> NotificationPreference:
        """Update preferences for a user."""
        pref = self.get_or_create(user_id)
        allowed_fields = {
            "early_leave_alerts",
            "anomaly_alerts",
            "attendance_confirmation",
            "low_attendance_warning",
            "daily_digest",
            "weekly_digest",
            "email_enabled",
            "low_attendance_threshold",
        }
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(pref, key, value)
        self.db.commit()
        self.db.refresh(pref)
        return pref
