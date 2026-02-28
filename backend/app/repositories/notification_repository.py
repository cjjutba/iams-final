"""
Notification Repository

Data access layer for Notification operations.
"""

import uuid as _uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.utils.exceptions import NotFoundError


def _to_uuid(value: str) -> _uuid.UUID:
    """Convert a string to uuid.UUID so SQLAlchemy UUID columns work on SQLite."""
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(value)


class NotificationRepository:
    """Repository for Notification CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        """Get notification by ID"""
        return self.db.query(Notification).filter(
            Notification.id == _to_uuid(notification_id)
        ).first()

    def get_by_user(
        self,
        user_id: str,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> List[Notification]:
        """
        Get notifications for a user

        Args:
            user_id: User UUID
            unread_only: If True, only return unread notifications
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of notifications sorted by created_at descending
        """
        query = self.db.query(Notification).filter(Notification.user_id == _to_uuid(user_id))

        if unread_only:
            query = query.filter(Notification.read == False)

        return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user"""
        return self.db.query(Notification).filter(
            Notification.user_id == _to_uuid(user_id),
            Notification.read == False
        ).count()

    def create(self, notification_data: dict) -> Notification:
        """
        Create a new notification

        Args:
            notification_data: Notification data dictionary

        Returns:
            Created notification
        """
        notification = Notification(**notification_data)
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_as_read(self, notification_id: str) -> Notification:
        """
        Mark a notification as read

        Args:
            notification_id: Notification UUID

        Returns:
            Updated notification

        Raises:
            NotFoundError: If notification not found
        """
        notification = self.get_by_id(notification_id)
        if not notification:
            raise NotFoundError(f"Notification not found: {notification_id}")

        notification.read = True
        notification.read_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user

        Args:
            user_id: User UUID

        Returns:
            Number of notifications updated
        """
        now = datetime.utcnow()
        count = self.db.query(Notification).filter(
            Notification.user_id == _to_uuid(user_id),
            Notification.read == False
        ).update({
            "read": True,
            "read_at": now
        })
        self.db.commit()
        return count
