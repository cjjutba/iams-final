"""
Audit Logging Utility

Helper function to record admin actions in both the legacy ``audit_logs``
table (for backwards compatibility with the audit router and any reports
that query it directly) AND the new unified ``activity_events`` timeline
(for the System Activity admin page + thesis evidence export).

One-direction unification:
  * ``log_audit()`` writes to ``audit_logs`` AND calls ``emit_event()``
    with an audit-category event.
  * Service-driven ``emit_event()`` calls (e.g. MARKED_PRESENT from
    presence_service, RECOGNITION_MATCH from realtime_pipeline) do NOT
    call ``log_audit()`` — they aren't admin actions and shouldn't land
    in the audit_logs table.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


# Default mapping from (action, target_type) to activity_events.event_type.
# Callers can override by passing ``activity_event_type`` explicitly.
_DEFAULT_ACTIVITY_MAP: dict[tuple[str, str], str] = {
    # Auth
    ("login", "admin"): "ADMIN_LOGIN",
    ("login", "faculty"): "FACULTY_LOGIN",
    ("login", "student"): "STUDENT_LOGIN",
    # User CRUD
    ("create", "user"): "USER_CREATED",
    ("update", "user"): "USER_UPDATED",
    ("delete", "user"): "USER_DELETED",
    ("deactivate", "user"): "USER_UPDATED",
    ("reactivate", "user"): "USER_UPDATED",
    # Face / registration
    ("approve", "face_registration"): "FACE_REGISTRATION_APPROVED",
    # Settings
    ("update", "settings"): "SETTINGS_CHANGED",
    ("update", "system_setting"): "SETTINGS_CHANGED",
    # Schedule CRUD (added 2026-04-25 — System Activity overhaul)
    ("create", "schedule"): "SCHEDULE_CREATED",
    ("update", "schedule"): "SCHEDULE_UPDATED",
    ("delete", "schedule"): "SCHEDULE_DELETED",
    # Enrollments (manual via admin)
    ("create", "enrollment"): "ENROLLMENT_ADDED",
    ("delete", "enrollment"): "ENROLLMENT_REMOVED",
}


def _derive_activity_event_type(
    action: str,
    target_type: str,
    explicit: Optional[str],
) -> Optional[str]:
    """Pick an activity event_type string for the given audit row."""
    if explicit:
        return explicit
    return _DEFAULT_ACTIVITY_MAP.get((action.lower(), target_type.lower()))


def log_audit(
    db: Session,
    admin_id,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: str | None = None,
    *,
    activity_event_type: Optional[str] = None,
    activity_summary: Optional[str] = None,
    activity_payload: Optional[dict[str, Any]] = None,
    activity_severity: str = "info",
):
    """Record an admin action.

    Writes one row to ``audit_logs`` (the existing table) and ALSO emits
    an ``activity_events`` row when a mapping exists for
    ``(action, target_type)`` — so the admin's System Activity page sees
    the audit action alongside attendance / recognition / session events.

    Args:
        db: DB session.
        admin_id: UUID of the admin performing the action.
        action: Action verb (e.g. 'create', 'update', 'delete', 'login').
        target_type: Type of entity acted upon (e.g. 'user', 'schedule').
        target_id: Optional target entity ID (stringified).
        details: Optional free-text / JSON details — stored verbatim in
            ``audit_logs.details``.
        activity_event_type: Optional explicit activity event type; when
            omitted it's derived from ``(action, target_type)`` via
            ``_DEFAULT_ACTIVITY_MAP``. Pass ``None`` to suppress the
            activity emit entirely.
        activity_summary: Optional human-readable summary for the
            activity row. When omitted a reasonable default is built.
        activity_payload: Optional structured payload for activity_events.
        activity_severity: Severity bucket — default "info".
    """
    try:
        log = AuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.exception(
            "log_audit: failed to write audit_logs row (action=%s, target=%s)",
            action,
            target_type,
        )
        # Continue to the activity emit — losing one but not both is worse.

    # Emit matching activity event when we have a mapping.
    derived_type = _derive_activity_event_type(
        action, target_type, activity_event_type
    )
    if derived_type is None:
        return

    try:
        from app.services.activity_service import emit_audit_event

        summary = activity_summary or (
            f"{action.upper()} on {target_type}"
            + (f" ({target_id})" if target_id else "")
        )
        subject_user_id = target_id if target_type.lower() == "user" else None
        subject_schedule_id = (
            target_id if target_type.lower() == "schedule" else None
        )

        emit_audit_event(
            db,
            event_type=derived_type,
            summary=summary,
            actor_id=str(admin_id) if admin_id else None,
            subject_user_id=subject_user_id,
            subject_schedule_id=subject_schedule_id,
            severity=activity_severity,
            payload=activity_payload
            or {
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "details": details,
            },
            autocommit=True,
        )
    except Exception:
        logger.exception(
            "log_audit: failed to emit activity event (action=%s, target=%s)",
            action,
            target_type,
        )
