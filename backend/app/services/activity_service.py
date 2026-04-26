"""
Activity Service — single-entry helper for emitting domain events.

Every meaningful system transition — attendance verdicts, session
lifecycle, recognition-identity transitions (downsampled at emit site),
admin audit, and system health — flows through :func:`emit_event`. It
writes an immutable row into ``activity_events`` (shared with the
caller's DB transaction by default) and fires a best-effort WebSocket
broadcast via the existing ``ws_manager`` infrastructure.

Design principles:

* **Never raises.** All failures are logged and swallowed. The activity
  log must never break the caller's control flow.
* **Atomic with the caller's state change.** Default ``autocommit=False``
  uses ``db.flush()`` — the event row commits iff the caller's
  transaction commits. Standalone callers pass ``autocommit=True``.
* **Fire-and-forget WebSocket fanout.** Broadcast is scheduled on the
  running event loop. Sync callers in a request context still reach it;
  sync callers outside a loop (e.g. background threads) simply skip the
  WS step with a debug log.
* **Cardinality gating at emit site.** Recognition events are emitted
  only on tracker identity transitions via existing bookkeeping in
  ``realtime_pipeline.py`` — not once per frame.
* **One-direction unification with audit.** ``log_audit()`` calls
  ``emit_event()`` internally; service-driven ``emit_event()`` calls do
  NOT call ``log_audit()``. Only admin-action audit rows land in both
  tables.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical event type constants.
#
# Keep this list greppable — every string used in a switch/filter across the
# codebase should be a member of this class. If you want to add a new event
# type, add it here first, then reference the constant at the emit site.
# ---------------------------------------------------------------------------


class EventType:
    """Canonical event type identifiers for activity_events.event_type."""

    # Attendance (5)
    MARKED_PRESENT = "MARKED_PRESENT"
    MARKED_LATE = "MARKED_LATE"
    MARKED_ABSENT = "MARKED_ABSENT"
    EARLY_LEAVE_FLAGGED = "EARLY_LEAVE_FLAGGED"
    EARLY_LEAVE_RETURNED = "EARLY_LEAVE_RETURNED"

    # Session (4)
    SESSION_STARTED_AUTO = "SESSION_STARTED_AUTO"
    SESSION_STARTED_MANUAL = "SESSION_STARTED_MANUAL"
    SESSION_ENDED_AUTO = "SESSION_ENDED_AUTO"
    SESSION_ENDED_MANUAL = "SESSION_ENDED_MANUAL"

    # Recognition (2) — downsampled at emit site to one per tracker transition
    RECOGNITION_MATCH = "RECOGNITION_MATCH"
    RECOGNITION_MISS = "RECOGNITION_MISS"

    # System (5) — pipeline + camera health
    PIPELINE_STARTED = "PIPELINE_STARTED"
    PIPELINE_STOPPED = "PIPELINE_STOPPED"
    PIPELINE_CAMERA_SWAPPED = "PIPELINE_CAMERA_SWAPPED"
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    CAMERA_ONLINE = "CAMERA_ONLINE"

    # Audit (13) — emitted by log_audit() indirection only.
    # Schedule + enrollment CRUD added 2026-04-25 to close the
    # "no admin action gets logged" gap surfaced by the System
    # Activity overhaul.
    ADMIN_LOGIN = "ADMIN_LOGIN"
    FACULTY_LOGIN = "FACULTY_LOGIN"
    STUDENT_LOGIN = "STUDENT_LOGIN"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    FACE_REGISTRATION_APPROVED = "FACE_REGISTRATION_APPROVED"
    SETTINGS_CHANGED = "SETTINGS_CHANGED"
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_UPDATED = "SCHEDULE_UPDATED"
    SCHEDULE_DELETED = "SCHEDULE_DELETED"
    ENROLLMENT_ADDED = "ENROLLMENT_ADDED"
    ENROLLMENT_REMOVED = "ENROLLMENT_REMOVED"


class EventCategory:
    ATTENDANCE = "attendance"
    SESSION = "session"
    RECOGNITION = "recognition"
    SYSTEM = "system"
    AUDIT = "audit"


class EventSeverity:
    INFO = "info"
    SUCCESS = "success"
    WARN = "warn"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------


def emit_event(
    db: Session,
    *,
    event_type: str,
    category: str,
    summary: str,
    severity: str = EventSeverity.INFO,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    subject_user_id: Optional[str] = None,
    subject_schedule_id: Optional[str] = None,
    subject_room_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    ref_attendance_id: Optional[str] = None,
    ref_early_leave_id: Optional[str] = None,
    ref_recognition_event_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    autocommit: bool = False,
) -> Optional[str]:
    """Persist an activity event + best-effort WebSocket broadcast.

    Args:
        db: Shared DB session. When the caller already has an active
            transaction, leave ``autocommit=False`` and the event becomes
            atomic with the caller's commit.
        event_type: One of :class:`EventType` constants.
        category: One of :class:`EventCategory` constants.
        summary: Human-readable one-line description for list rendering.
        severity: One of :class:`EventSeverity` constants.
        actor_type: ``system | user | pipeline``.
        actor_id, subject_*_id, camera_id, ref_*_id: Optional context.
        payload: Optional JSONB payload for the event detail sheet +
            CSV/JSON export. Keep under ~2 KB — use IDs not full objects.
        autocommit: When True, commit the new row immediately. When False
            (default), ``db.flush()`` only — caller commits later.

    Returns:
        The event UUID as string on success, ``None`` on any failure.
        Never raises.
    """
    event_id: Optional[str] = None

    try:
        event = ActivityEvent(
            event_type=event_type,
            category=category,
            severity=severity,
            actor_type=actor_type,
            actor_id=actor_id,
            subject_user_id=subject_user_id,
            subject_schedule_id=subject_schedule_id,
            subject_room_id=subject_room_id,
            camera_id=camera_id,
            ref_attendance_id=ref_attendance_id,
            ref_early_leave_id=ref_early_leave_id,
            ref_recognition_event_id=ref_recognition_event_id,
            summary=summary,
            payload=payload,
        )
        db.add(event)
        if autocommit:
            db.commit()
            db.refresh(event)
        else:
            db.flush()  # assigns id + makes visible in same tx, no commit

        event_id = str(event.id)

        # Snapshot a serialisable dict for the WS broadcast — we can't
        # safely hand the ORM instance across the task boundary.
        broadcast_dict = _serialise_for_broadcast(event)
    except Exception:
        logger.exception(
            "emit_event: DB write failed (event_type=%s, category=%s)",
            event_type,
            category,
        )
        # Caller's transaction may now be in a dirty state — but we
        # deliberately do NOT rollback, because the caller owns the tx
        # and may have already written more.
        return None

    # Fire-and-forget WebSocket broadcast. If no loop is running (e.g.
    # the call came from a background thread or test fixture), log and
    # skip — the row is still persisted.
    _schedule_broadcast(broadcast_dict)

    return event_id


def _serialise_for_broadcast(event: ActivityEvent) -> dict[str, Any]:
    """Build the JSON-safe dict that ws_manager.broadcast_activity() sends.

    Includes ``actor_name`` / ``subject_user_name`` / ``subject_schedule_subject``
    so the admin's live stream renders human labels in real time. Without
    these, freshly-arriving events display raw UUIDs in the summary
    (the formatter does UUID-to-name substitution on the client). The
    REST list endpoint enriches the same fields server-side; we mirror
    its shape here so REST and WS payloads stay interchangeable.
    """

    def _id(x):
        return str(x) if x is not None else None

    # Resolve relationship names lazily. The relationships are configured
    # on the model with default lazy='select', so accessing them issues
    # one SELECT each — fine for the emit-time path which is already
    # writing a row in the same transaction. Wrap in try/except because:
    #  - the session might be closed by the time the broadcast task fires
    #    (we serialise *before* scheduling the task, so usually OK)
    #  - test fixtures sometimes pass detached events
    # If anything goes wrong, the broadcast still ships with a null name
    # and the client gracefully falls back to the raw UUID display.
    actor_name: str | None = None
    subject_user_name: str | None = None
    subject_user_student_id: str | None = None
    subject_schedule_subject: str | None = None
    try:
        if event.actor is not None:
            first = getattr(event.actor, "first_name", "") or ""
            last = getattr(event.actor, "last_name", "") or ""
            actor_name = f"{first} {last}".strip() or None
    except Exception:
        logger.debug("activity broadcast: failed to resolve actor name", exc_info=True)
    try:
        if event.subject_user is not None:
            first = getattr(event.subject_user, "first_name", "") or ""
            last = getattr(event.subject_user, "last_name", "") or ""
            subject_user_name = f"{first} {last}".strip() or None
            # User.student_id is the human-facing record number — the
            # admin's "View student" drilldown URL needs THIS value, not
            # the user UUID. Mirror what the REST list endpoint emits.
            subject_user_student_id = (
                getattr(event.subject_user, "student_id", None) or None
            )
    except Exception:
        logger.debug(
            "activity broadcast: failed to resolve subject_user name",
            exc_info=True,
        )
    try:
        if event.schedule is not None:
            subject_schedule_subject = getattr(event.schedule, "subject_code", None)
    except Exception:
        logger.debug(
            "activity broadcast: failed to resolve schedule subject_code",
            exc_info=True,
        )

    return {
        "type": "activity_event",
        "event_id": str(event.id),
        "event_type": event.event_type,
        "category": event.category,
        "severity": event.severity,
        "actor_type": event.actor_type,
        "actor_id": _id(event.actor_id),
        "actor_name": actor_name,
        "subject_user_id": _id(event.subject_user_id),
        "subject_user_name": subject_user_name,
        "subject_user_student_id": subject_user_student_id,
        "subject_schedule_id": _id(event.subject_schedule_id),
        "subject_schedule_subject": subject_schedule_subject,
        "subject_room_id": _id(event.subject_room_id),
        "camera_id": event.camera_id,
        "ref_attendance_id": _id(event.ref_attendance_id),
        "ref_early_leave_id": _id(event.ref_early_leave_id),
        "ref_recognition_event_id": _id(event.ref_recognition_event_id),
        "summary": event.summary,
        "payload": event.payload,
        "created_at": (event.created_at or datetime.now()).isoformat(),
    }


def _schedule_broadcast(event_dict: dict[str, Any]) -> None:
    """Schedule `ws_manager.broadcast_activity()` on the running loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug(
            "emit_event: no running loop for activity WS broadcast — skipping"
        )
        return

    loop.create_task(_do_broadcast(event_dict))


async def _do_broadcast(event_dict: dict[str, Any]) -> None:
    try:
        from app.routers.websocket import ws_manager

        await ws_manager.broadcast_activity(event_dict)
    except Exception:
        logger.exception("Activity WS broadcast failed")


# ---------------------------------------------------------------------------
# Convenience wrappers — keep call sites terse and self-documenting.
# ---------------------------------------------------------------------------


def emit_attendance_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    schedule_id: str,
    student_id: str,
    attendance_id: Optional[str] = None,
    severity: str = EventSeverity.INFO,
    actor_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    autocommit: bool = False,
) -> Optional[str]:
    """Convenience wrapper for attendance-category events."""
    return emit_event(
        db,
        event_type=event_type,
        category=EventCategory.ATTENDANCE,
        severity=severity,
        summary=summary,
        actor_type="pipeline",
        actor_id=actor_id,
        subject_user_id=student_id,
        subject_schedule_id=schedule_id,
        ref_attendance_id=attendance_id,
        payload=payload,
        autocommit=autocommit,
    )


def emit_session_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    schedule_id: str,
    room_id: Optional[str] = None,
    severity: str = EventSeverity.INFO,
    actor_id: Optional[str] = None,
    actor_type: str = "system",
    payload: Optional[dict[str, Any]] = None,
    autocommit: bool = False,
) -> Optional[str]:
    """Convenience wrapper for session-category events."""
    return emit_event(
        db,
        event_type=event_type,
        category=EventCategory.SESSION,
        severity=severity,
        summary=summary,
        actor_type=actor_type,
        actor_id=actor_id,
        subject_schedule_id=schedule_id,
        subject_room_id=room_id,
        payload=payload,
        autocommit=autocommit,
    )


def emit_audit_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor_id: str,
    subject_user_id: Optional[str] = None,
    subject_schedule_id: Optional[str] = None,
    severity: str = EventSeverity.INFO,
    payload: Optional[dict[str, Any]] = None,
    autocommit: bool = False,
) -> Optional[str]:
    """Convenience wrapper for audit-category events.

    Called indirectly by ``app.utils.audit.log_audit()`` — direct callers
    should prefer ``log_audit()`` so the AuditLog row also lands.
    """
    return emit_event(
        db,
        event_type=event_type,
        category=EventCategory.AUDIT,
        severity=severity,
        summary=summary,
        actor_type="user",
        actor_id=actor_id,
        subject_user_id=subject_user_id,
        subject_schedule_id=subject_schedule_id,
        payload=payload,
        autocommit=autocommit,
    )


def emit_recognition_transition(
    db: Session,
    *,
    event_type: str,
    summary: str,
    schedule_id: str,
    camera_id: str,
    student_id: Optional[str] = None,
    ref_recognition_event_id: Optional[str] = None,
    severity: str = EventSeverity.INFO,
    payload: Optional[dict[str, Any]] = None,
    autocommit: bool = False,
) -> Optional[str]:
    """Convenience wrapper for recognition-identity transitions.

    Emit once per tracker identity transition (first match, first
    confirmed-unknown) — NOT per frame.
    """
    return emit_event(
        db,
        event_type=event_type,
        category=EventCategory.RECOGNITION,
        severity=severity,
        summary=summary,
        actor_type="pipeline",
        subject_user_id=student_id,
        subject_schedule_id=schedule_id,
        camera_id=camera_id,
        ref_recognition_event_id=ref_recognition_event_id,
        payload=payload,
        autocommit=autocommit,
    )


def emit_system_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    severity: str = EventSeverity.INFO,
    schedule_id: Optional[str] = None,
    room_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    autocommit: bool = True,
) -> Optional[str]:
    """Convenience wrapper for system-health events.

    Defaults to ``autocommit=True`` because system events are typically
    fired outside a request transaction (pipeline startup/shutdown,
    camera health).
    """
    return emit_event(
        db,
        event_type=event_type,
        category=EventCategory.SYSTEM,
        severity=severity,
        summary=summary,
        actor_type="system",
        subject_schedule_id=schedule_id,
        subject_room_id=room_id,
        camera_id=camera_id,
        payload=payload,
        autocommit=autocommit,
    )
