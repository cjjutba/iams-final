"""
VPS sync sender — pushes faculty/admin users + rooms + schedules +
faculty_records from the on-prem Mac to the VPS receiver.

Wired into ``app/main.py``'s APScheduler block when ``ENABLE_VPS_SYNC=true``.
The job runs every ``VPS_SYNC_INTERVAL_SECONDS`` (default 300). Each tick
pushes the *full* state of the four tables — there is no delta /
watermark, so a missed tick has no consistency impact.

Why polling, not event-driven
-----------------------------
The four sync'd tables change rarely (≈once per term in steady state)
and the latency budget is "minutes" — the faculty APK doesn't care if a
new schedule appears 4 minutes after admin creates it. Event-driven
sync would mean wiring write hooks into every CREATE/UPDATE/DELETE path
across the routers + admin portal, which is a much larger surface to
keep correct than one timer that re-pushes everything.

Failure handling
----------------
Network errors / 5xx responses raise — ``with_failure_notification``
wrapping in main.py catches and emits a one-hour-deduped admin alert.
A missed tick has no impact: the next tick re-pushes the full snapshot.

The job is also a no-op when ``VPS_SYNC_URL`` or ``VPS_SYNC_SECRET`` is
empty so a partially-configured deployment doesn't fire alerts every
tick before the operator finishes setup.
"""

from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.faculty_record import FacultyRecord
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


# ───────────────────────── serializers ────────────────────────────────────


def _serialize_user(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id),
        "email": u.email,
        "password_hash": u.password_hash,
        # ``UserRole`` is a StrEnum — ``.value`` gives the lowercase
        # canonical form ("faculty" / "admin"). The receiver accepts both
        # forms (see ``_parse_role`` in routers/sync.py) so even a renamed
        # enum on one side won't break the wire format.
        "role": u.role.value,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "phone": u.phone,
        "student_id": u.student_id,
        "supabase_user_id": u.supabase_user_id,
        "email_verified": u.email_verified,
        "email_verified_at": u.email_verified_at.isoformat() if u.email_verified_at else None,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat(),
        "updated_at": u.updated_at.isoformat(),
    }


def _serialize_room(r: Room) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "name": r.name,
        "building": r.building,
        "capacity": r.capacity,
        "camera_endpoint": r.camera_endpoint,
        "stream_key": r.stream_key,
        "is_active": r.is_active,
    }


def _serialize_schedule(s: Schedule) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "subject_code": s.subject_code,
        "subject_name": s.subject_name,
        "faculty_id": str(s.faculty_id),
        "room_id": str(s.room_id),
        "day_of_week": s.day_of_week,
        # ``time`` objects → "HH:MM:SS" strings.
        "start_time": s.start_time.isoformat(),
        "end_time": s.end_time.isoformat(),
        "semester": s.semester,
        "academic_year": s.academic_year,
        "target_course": s.target_course,
        "target_year_level": s.target_year_level,
        "early_leave_timeout_minutes": s.early_leave_timeout_minutes,
        "is_active": s.is_active,
    }


def _serialize_faculty_record(fr: FacultyRecord) -> dict[str, Any]:
    return {
        "faculty_id": fr.faculty_id,
        "first_name": fr.first_name,
        "last_name": fr.last_name,
        "email": fr.email,
        "department": fr.department,
        "is_active": fr.is_active,
        "created_at": fr.created_at.isoformat() if fr.created_at else None,
    }


# ───────────────────────── job entrypoint ─────────────────────────────────


async def run_vps_sync() -> None:
    """Push the four sync'd tables to the VPS receiver.

    Wrapped at registration time by ``with_failure_notification("vps_sync")``
    in ``app/main.py``, so an unhandled exception here surfaces as a
    deduped admin notification.
    """
    if not settings.ENABLE_VPS_SYNC:
        # Defence in depth — the registration site already gates on this
        # flag, but a runtime config flip should be respected.
        return

    if not settings.VPS_SYNC_URL or not settings.VPS_SYNC_SECRET:
        logger.warning(
            "[vps_sync] ENABLE_VPS_SYNC=true but VPS_SYNC_URL/SECRET not "
            "configured — skipping tick. Set them in scripts/.env.local."
        )
        return

    # ── Snapshot phase ────────────────────────────────────────────────
    # Read all four tables under one short-lived session. The data
    # volume is tiny so we don't paginate; everything fits comfortably
    # in memory.
    db = SessionLocal()
    try:
        faculty_records = [
            _serialize_faculty_record(fr) for fr in db.query(FacultyRecord).all()
        ]
        users = [
            _serialize_user(u)
            for u in (
                db.query(User)
                .filter(User.role.in_([UserRole.FACULTY, UserRole.ADMIN]))
                .all()
            )
        ]
        rooms = [_serialize_room(r) for r in db.query(Room).all()]
        schedules = [_serialize_schedule(s) for s in db.query(Schedule).all()]
    finally:
        db.close()

    # ── Push phase ────────────────────────────────────────────────────
    payload = {
        "faculty_records": faculty_records,
        "users": users,
        "rooms": rooms,
        "schedules": schedules,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "source_host": socket.gethostname(),
    }

    headers = {
        "X-Sync-Secret": settings.VPS_SYNC_SECRET,
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.VPS_SYNC_TIMEOUT_SECONDS)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(
                settings.VPS_SYNC_URL,
                json=payload,
                headers=headers,
            )
        except httpx.RequestError as exc:
            # Connection errors, DNS failures, timeouts — re-raise so
            # ``with_failure_notification`` deduped-alerts the operator.
            # The Mac → VPS link being flaky for a few minutes is not
            # itself a problem (next tick recovers); but if it stays
            # flaky for an hour, the operator wants to know.
            logger.warning(
                "[vps_sync] transport error pushing to %s: %s",
                settings.VPS_SYNC_URL,
                exc,
            )
            raise

    if resp.status_code != 200:
        # Bubble HTTP errors up. 401 = secret mismatch (operator config
        # bug, alert worth firing). 503 = receiver disabled on VPS.
        # 400 = sender-side bug (e.g. zero users) — investigate.
        logger.warning(
            "[vps_sync] receiver responded %d: %s",
            resp.status_code,
            resp.text[:300],
        )
        resp.raise_for_status()

    body = resp.json()
    counts = body.get("counts", {})
    summary = ", ".join(
        f"{k}=+{v.get('upserted', 0)}/-{v.get('deleted', 0)}"
        for k, v in counts.items()
    )
    logger.info(
        "[vps_sync] OK — pushed faculty_records=%d users=%d rooms=%d schedules=%d → %s [%s]",
        len(faculty_records),
        len(users),
        len(rooms),
        len(schedules),
        settings.VPS_SYNC_URL,
        summary,
    )
