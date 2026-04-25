"""
Notification Repository

Data access layer for Notification operations.
"""

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.utils.exceptions import NotFoundError


def _utcnow() -> datetime:
    """Timezone-aware UTC now — mirrors the model default."""
    return datetime.now(timezone.utc)


def _to_uuid(value: str) -> _uuid.UUID:
    """Convert a string to uuid.UUID so SQLAlchemy UUID columns work on SQLite."""
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(value)


class NotificationRepository:
    """Repository for Notification CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notification_id: str) -> Notification | None:
        """Get notification by ID"""
        return self.db.query(Notification).filter(Notification.id == _to_uuid(notification_id)).first()

    def get_by_user(
        self,
        user_id: str,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
        severity: str | None = None,
        notification_type: str | None = None,
    ) -> list[Notification]:
        """
        Get notifications for a user

        Args:
            user_id: User UUID
            unread_only: If True, only return unread notifications
            skip: Number of records to skip
            limit: Maximum number of records to return
            severity: Optional severity filter (info/success/warn/error/critical).
            notification_type: Optional notification ``type`` filter.

        Returns:
            List of notifications sorted by created_at descending
        """
        query = self.db.query(Notification).filter(Notification.user_id == _to_uuid(user_id))

        if unread_only:
            query = query.filter(Notification.read.is_(False))

        if severity is not None:
            query = query.filter(Notification.severity == severity)

        if notification_type is not None:
            query = query.filter(Notification.type == notification_type)

        return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user"""
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == _to_uuid(user_id), Notification.read.is_(False))
            .count()
        )

    def get_unread_critical_count(self, user_id: str) -> int:
        """Count unread notifications with severity in ('error', 'critical').

        Used to drive the admin sidebar's red badge — distinguishes
        action-needed from informational.
        """
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == _to_uuid(user_id),
                Notification.read.is_(False),
                Notification.severity.in_(("error", "critical")),
            )
            .count()
        )

    def create(self, notification_data: dict, *, severity: str = "info") -> Notification:
        """
        Create a new notification.

        Args:
            notification_data: Notification data dictionary. May or may not
                contain a ``severity`` key — if absent the ``severity``
                keyword argument below is used.
            severity: Severity tag (``info``/``success``/``warn``/``error``/
                ``critical``). Only applied when ``notification_data`` does
                NOT already include a ``severity`` key.

        Returns:
            Created notification
        """
        # Allow callers to pass severity either via the data dict (existing
        # callers may add it there) or as a keyword argument. The dict wins
        # if both are present, so older callsites keep working unchanged.
        data = dict(notification_data)
        data.setdefault("severity", severity)
        notification = Notification(**data)
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def exists_recent(
        self,
        user_id: str,
        notification_type: str,
        within_seconds: int,
        reference_id: str | None = None,
    ) -> bool:
        """Return True if a matching notification was created within the window.

        Used by ``notification_service.notify()`` to throttle duplicate alerts
        (e.g. the auto-start scheduler emitting ``Session Started`` for
        ``TEST 226`` every time the pipeline self-heals).

        Args:
            user_id: Recipient UUID.
            notification_type: Type tag to match (e.g. ``session_start``).
            within_seconds: Lookback window in seconds.
            reference_id: If provided, must also match on reference_id.
        """
        if within_seconds <= 0:
            return False
        cutoff = _utcnow() - timedelta(seconds=within_seconds)
        q = self.db.query(Notification).filter(
            Notification.user_id == _to_uuid(user_id),
            Notification.type == notification_type,
            Notification.created_at >= cutoff,
        )
        if reference_id is not None:
            q = q.filter(Notification.reference_id == reference_id)
        return self.db.query(q.exists()).scalar() is True

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
        notification.read_at = _utcnow()
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
        now = _utcnow()
        count = (
            self.db.query(Notification)
            .filter(Notification.user_id == _to_uuid(user_id), Notification.read.is_(False))
            .update({"read": True, "read_at": now})
        )
        self.db.commit()
        return count

    def delete(self, notification_id: str) -> bool:
        """Delete a notification by ID. Returns True if deleted."""
        notification = self.get_by_id(notification_id)
        if not notification:
            return False
        self.db.delete(notification)
        self.db.commit()
        return True

    def delete_all(self, user_id: str) -> int:
        """Delete all notifications for a user. Returns count deleted."""
        count = self.db.query(Notification).filter(Notification.user_id == _to_uuid(user_id)).delete()
        self.db.commit()
        return count
