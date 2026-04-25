"""
Notification Service — Central orchestrator for all notification delivery.

Every event that should notify a user flows through ``notify()`` which
coordinates three delivery channels:

1. **In-app** — always creates a ``Notification`` DB row
2. **Toast (WebSocket)** — pushes to ``/ws/alerts/{user_id}`` (fire-and-forget)
3. **Email** — sends via Resend if enabled (fire-and-forget)
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

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
    severity: str = "info",
    send_email: bool = False,
    email_template: str | None = None,
    email_context: dict | None = None,
    dedup_window_seconds: int = 0,
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
        severity: Persisted severity tag stored on the Notification row and
            included in the WebSocket payload. One of
            ``info``/``success``/``warn``/``error``/``critical``. Drives the
            unread-critical badge query and frontend styling.
        send_email: Whether this trigger can produce an email.
        email_template: Template name for ``EmailService`` (e.g. ``check_in``).
        email_context: Template variables dict.
        dedup_window_seconds: If >0, skip delivery (DB + WS + email) when a
            notification of the same ``notification_type`` (and
            ``reference_id`` if provided) already exists for this user within
            the last N seconds. Prevents duplicate toasts from restart /
            self-heal cycles.
    """

    repo = NotificationRepository(db)

    # ── 0. Dedup — short-circuit repeats of the same event ───────
    if dedup_window_seconds > 0:
        try:
            if repo.exists_recent(
                user_id=user_id,
                notification_type=notification_type,
                within_seconds=dedup_window_seconds,
                reference_id=reference_id,
            ):
                logger.debug(
                    "notify(): deduped %s for user=%s ref=%s within %ss",
                    notification_type,
                    user_id,
                    reference_id,
                    dedup_window_seconds,
                )
                return
        except Exception:
            # Dedup check is best-effort — never block delivery on it.
            logger.exception("notify(): dedup check failed, falling through")

    # ── 1. Check user preference ─────────────────────────────────
    if preference_key:
        pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if pref and not getattr(pref, preference_key, True):
            logger.debug(f"Notification suppressed for user {user_id}: {preference_key} disabled")
            return

    # ── 2. Create DB row (always) ────────────────────────────────
    try:
        repo.create(
            {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type,
                "severity": severity,
                "reference_id": reference_id,
                "reference_type": reference_type,
            },
            severity=severity,
        )
    except Exception:
        logger.exception(f"Failed to persist notification for user {user_id}")

    # ── 3. WebSocket toast (fire-and-forget) ─────────────────────
    try:
        from app.routers.websocket import ws_manager

        await ws_manager.broadcast_alert(
            user_id,
            {
                "type": "notification",
                "toast_type": toast_type,
                "severity": severity,
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "reference_id": reference_id,
                "reference_type": reference_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        logger.exception(f"Failed to push WS toast for user {user_id}")

    # ── 4. Email (fire-and-forget, gated) ────────────────────────
    if send_email and settings.EMAIL_ENABLED and email_template:
        try:
            # Check user-level email_enabled
            pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
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


# ── Role / Schedule fan-out helpers (Phase 1) ─────────────────────────────
#
# These are role-aware convenience wrappers around ``notify()`` so callers
# don't have to query for recipients themselves. They are deliberately
# tolerant of the empty case (return 0 instead of raising) and forward
# all kwargs to ``notify()`` so per-call severity / dedup / preference_key
# semantics stay consistent.


async def notify_admins(
    db: Session,
    title: str,
    message: str,
    notification_type: str,
    *,
    exclude_user_id: UUID | None = None,
    **kwargs,
) -> int:
    """Fan out a notification to every active admin user.

    Returns the number of recipients notified. Forwards all additional
    keyword arguments (severity, preference_key, send_email,
    dedup_window_seconds, etc.) to :func:`notify`.

    Safe when zero admins exist — returns 0 without raising.
    """
    from app.models.user import User, UserRole

    admins = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
        .all()
    )

    sent = 0
    for admin in admins:
        if exclude_user_id is not None and admin.id == exclude_user_id:
            continue
        await notify(
            db,
            str(admin.id),
            title,
            message,
            notification_type,
            **kwargs,
        )
        sent += 1
    return sent


async def notify_role(
    db: Session,
    role,
    title: str,
    message: str,
    notification_type: str,
    *,
    exclude_user_id: UUID | None = None,
    **kwargs,
) -> int:
    """Fan out a notification to every active user with the given ``role``.

    ``role`` is a :class:`~app.models.user.UserRole` enum value.

    Returns the number of recipients notified. Safe when no matching
    users exist — returns 0 without raising.
    """
    from app.models.user import User

    users = (
        db.query(User)
        .filter(User.role == role, User.is_active.is_(True))
        .all()
    )

    sent = 0
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        await notify(
            db,
            str(user.id),
            title,
            message,
            notification_type,
            **kwargs,
        )
        sent += 1
    return sent


async def notify_schedule_participants(
    db: Session,
    schedule_id: UUID,
    title: str,
    message: str,
    notification_type: str,
    *,
    include_admins: bool = False,
    exclude_user_id: UUID | None = None,
    **kwargs,
) -> int:
    """Fan out a notification to all participants of a schedule.

    Recipients:
        * the faculty assigned to the schedule
        * all students enrolled in the schedule
        * optionally every active admin (when ``include_admins=True``)

    Returns the number of recipients notified. Safe when the schedule
    is missing or has no enrollments — returns 0 without raising.
    """
    from app.models.enrollment import Enrollment
    from app.models.schedule import Schedule
    from app.models.user import User, UserRole

    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if schedule is None:
        return 0

    # Collect unique recipient IDs first so a single user enrolled +
    # admin doesn't get the same alert twice in one call.
    recipient_ids: set[UUID] = set()

    if schedule.faculty_id is not None:
        recipient_ids.add(schedule.faculty_id)

    enrollment_rows = (
        db.query(Enrollment.student_id)
        .filter(Enrollment.schedule_id == schedule_id)
        .all()
    )
    for (student_id,) in enrollment_rows:
        recipient_ids.add(student_id)

    if include_admins:
        admin_rows = (
            db.query(User.id)
            .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .all()
        )
        for (admin_id,) in admin_rows:
            recipient_ids.add(admin_id)

    if exclude_user_id is not None:
        recipient_ids.discard(exclude_user_id)

    sent = 0
    for uid in recipient_ids:
        await notify(
            db,
            str(uid),
            title,
            message,
            notification_type,
            **kwargs,
        )
        sent += 1
    return sent
