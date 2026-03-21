"""
Notification Service — Central orchestrator for all notification delivery.

Every event that should notify a user flows through ``notify()`` which
coordinates three delivery channels:

1. **In-app** — always creates a ``Notification`` DB row
2. **Toast (WebSocket)** — pushes to ``/ws/alerts/{user_id}`` (fire-and-forget)
3. **Email** — sends via Resend if enabled (fire-and-forget)
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models.notification_preference import NotificationPreference
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


async def notify(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    *,
    preference_key: str | None = None,
    reference_id: str | None = None,
    reference_type: str | None = None,
    toast_type: str = "info",
    send_email: bool = False,
    email_template: str | None = None,
    email_context: dict | None = None,
):
    """
    Send a notification through all applicable channels.

    Args:
        db: Active SQLAlchemy session.
        user_id: Recipient user UUID.
        title: Notification title (shown in-app and toast).
        message: Notification body text.
        notification_type: Category tag (``check_in``, ``early_leave``, etc.).
        preference_key: Column name on ``NotificationPreference`` to check.
                        If the user disabled it, the notification is skipped entirely.
        reference_id: Optional FK to a related entity (attendance, event, …).
        reference_type: Describes what ``reference_id`` points to.
        toast_type: Toast severity — ``success``, ``warning``, ``error``, or ``info``.
        send_email: Whether this trigger can produce an email.
        email_template: Template name for ``EmailService`` (e.g. ``check_in``).
        email_context: Template variables dict.
    """

    # ── 1. Check user preference ─────────────────────────────────
    if preference_key:
        pref = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .first()
        )
        if pref and not getattr(pref, preference_key, True):
            logger.debug(
                f"Notification suppressed for user {user_id}: "
                f"{preference_key} disabled"
            )
            return

    # ── 2. Create DB row (always) ────────────────────────────────
    try:
        repo = NotificationRepository(db)
        repo.create({
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "reference_id": reference_id,
            "reference_type": reference_type,
        })
    except Exception:
        logger.exception(f"Failed to persist notification for user {user_id}")

    # ── 3. WebSocket toast (fire-and-forget) ─────────────────────
    try:
        from app.routers.websocket import ws_manager

        await ws_manager.broadcast_alert(user_id, {
            "type": "notification",
            "toast_type": toast_type,
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "reference_id": reference_id,
            "reference_type": reference_type,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception:
        logger.exception(f"Failed to push WS toast for user {user_id}")

    # ── 4. Email (fire-and-forget, gated) ────────────────────────
    if send_email and settings.EMAIL_ENABLED and email_template:
        try:
            # Check user-level email_enabled
            pref = (
                db.query(NotificationPreference)
                .filter(NotificationPreference.user_id == user_id)
                .first()
            )
            if pref and pref.email_enabled:
                from app.models.user import User

                user = db.query(User).filter(User.id == user_id).first()
                if user and user.email:
                    from app.services.email_service import EmailService

                    svc = EmailService()
                    await svc.send_notification_email(
                        to_email=user.email,
                        to_name=user.full_name or user.email,
                        template=email_template,
                        context=email_context or {},
                    )
        except Exception:
            logger.exception(f"Failed to send email for user {user_id}")


async def notify_many(
    db: Session,
    user_ids: list[str],
    title: str,
    message: str,
    notification_type: str,
    **kwargs,
):
    """
    Send the same notification to multiple users.

    Accepts all keyword arguments that ``notify()`` does.
    """
    for uid in user_ids:
        await notify(db, uid, title, message, notification_type, **kwargs)
