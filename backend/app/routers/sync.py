"""
VPS sync receiver — applies the Mac's faculty/schedule/room/faculty_record
snapshot to the local DB.

Wired into ``app/main.py`` only when ``ENABLE_SYNC_RECEIVER_ROUTES=true``,
which is the VPS thin profile. The on-prem Mac never mounts this router.

Authentication
--------------
Service-to-service via the ``X-Sync-Secret`` header compared against
``settings.VPS_SYNC_SECRET``. Constant-time comparison via
``hmac.compare_digest`` so a slow remote attacker can't time-side-channel
the secret. JWT-based admin auth would be a poor fit here: the sync runs
unattended, the Mac never has a "user session" to mint a token from, and
rotating the secret is a single env-var change instead of "log in, copy
token, paste".

Transactional model
-------------------
Each request applies inside one transaction:

  1. Upsert ``faculty_records`` (no FKs to other sync'd tables).
  2. Upsert ``users`` (no FKs to other sync'd tables; receiver is filtered
     to ``role IN (FACULTY, ADMIN)`` only — student PII never crosses
     this boundary).
  3. Upsert ``rooms`` (no FKs).
  4. Upsert ``schedules`` (FK to ``users.id`` and ``rooms.id`` — must
     happen after both parents).
  5. Delete rows whose PKs are NOT in the incoming set, FK-reverse
     order: schedules → rooms → users (faculty/admin only) → faculty_records.

A failure at any phase rolls back the whole tx — partial sync is never
visible to readers.

Safety guardrails
-----------------
- ``payload.users`` is rejected when empty: the Mac always has at least
  one admin user, so an empty list is almost certainly a Mac-side bug
  and would silently delete every VPS faculty/admin in one tick.
- Only deletes ``users`` whose ``role IN (FACULTY, ADMIN)``. If a row
  with a different role somehow ended up on the VPS (e.g. a stale
  pre-split row), it is left alone.
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.faculty_record import FacultyRecord
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


# ───────────────────────── request / response schemas ─────────────────────


class SyncRequest(BaseModel):
    """Payload pushed by the Mac sender. All four tables, full state.

    The receiver does not maintain a watermark; every push is a complete
    snapshot. This means a missed tick has zero impact on consistency —
    the next tick catches up automatically. That's why we don't need an
    outbox pattern.
    """

    faculty_records: list[dict[str, Any]] = Field(default_factory=list)
    users: list[dict[str, Any]] = Field(default_factory=list)
    rooms: list[dict[str, Any]] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)

    # Diagnostic only — surfaced in the response + logs so operators
    # debugging a desync can see when the snapshot was taken on the Mac
    # and which host produced it.
    sent_at: str | None = None
    source_host: str | None = None


class SyncTableCounts(BaseModel):
    upserted: int
    deleted: int


class SyncResponse(BaseModel):
    received_at: str
    source_host: str | None
    sent_at: str | None
    counts: dict[str, SyncTableCounts]


# ───────────────────────── helpers ────────────────────────────────────────


def _verify_secret(header_value: str | None) -> None:
    """Constant-time comparison against ``settings.VPS_SYNC_SECRET``."""
    expected = settings.VPS_SYNC_SECRET
    if not expected:
        # Receiver mounted but secret not configured → fail closed.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sync receiver not configured (VPS_SYNC_SECRET unset)",
        )
    if not header_value or not hmac.compare_digest(header_value, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sync secret",
        )


def _parse_dt(value: Any) -> datetime | None:
    """Tolerant ISO-8601 → datetime; None → None.

    The Mac sender always emits aware ISO-8601 strings, but historically
    some columns were naive. ``datetime.fromisoformat`` handles both.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _parse_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _parse_role(value: Any) -> UserRole:
    """Accept both StrEnum value ("faculty") and name ("FACULTY")."""
    raw = str(value)
    try:
        return UserRole(raw)
    except ValueError:
        try:
            return UserRole[raw.upper()]
        except KeyError as exc:
            raise ValueError(f"Unknown user role: {value!r}") from exc


# ───────────────────────── upsert helpers ─────────────────────────────────
#
# Each helper takes a list of incoming dicts, applies merge-by-PK on each,
# and returns the count it wrote. Counts are reported back to the Mac so
# operators can diff what the sender claimed it sent vs. what the receiver
# actually persisted.


def _upsert_faculty_records(db: Session, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        db.merge(
            FacultyRecord(
                faculty_id=row["faculty_id"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                department=row.get("department"),
                is_active=row.get("is_active", True),
                created_at=_parse_dt(row.get("created_at")) or datetime.now(),
            )
        )
    db.flush()
    return len(rows)


def _upsert_users(db: Session, rows: list[dict[str, Any]]) -> int:
    n = 0
    for row in rows:
        role = _parse_role(row["role"])
        # Defence in depth — even though the sender is filtered, never
        # write a STUDENT row from the wire onto the VPS DB.
        if role not in (UserRole.FACULTY, UserRole.ADMIN):
            logger.warning(
                "[sync] skipping inbound user with role=%s (id=%s) — only FACULTY/ADMIN are accepted on the VPS",
                role,
                row.get("id"),
            )
            continue
        db.merge(
            User(
                id=_parse_uuid(row["id"]),
                email=row["email"],
                password_hash=row["password_hash"],
                role=role,
                first_name=row["first_name"],
                last_name=row["last_name"],
                phone=row.get("phone"),
                student_id=row.get("student_id"),
                supabase_user_id=row.get("supabase_user_id"),
                email_verified=row.get("email_verified", False),
                email_verified_at=_parse_dt(row.get("email_verified_at")),
                is_active=row.get("is_active", True),
                created_at=_parse_dt(row.get("created_at")) or datetime.now(),
                updated_at=_parse_dt(row.get("updated_at")) or datetime.now(),
            )
        )
        n += 1
    db.flush()
    return n


def _upsert_rooms(db: Session, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        db.merge(
            Room(
                id=_parse_uuid(row["id"]),
                name=row["name"],
                building=row["building"],
                capacity=row.get("capacity"),
                camera_endpoint=row.get("camera_endpoint"),
                stream_key=row.get("stream_key"),
                is_active=row.get("is_active", True),
            )
        )
    db.flush()
    return len(rows)


def _upsert_schedules(db: Session, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        # ``start_time`` and ``end_time`` are ``time`` (no date) columns.
        # The sender serialises them as "HH:MM:SS" strings.
        from datetime import time as _time

        def _parse_time(v: Any) -> _time:
            if isinstance(v, _time):
                return v
            return _time.fromisoformat(str(v))

        db.merge(
            Schedule(
                id=_parse_uuid(row["id"]),
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                faculty_id=_parse_uuid(row["faculty_id"]),
                room_id=_parse_uuid(row["room_id"]),
                day_of_week=row["day_of_week"],
                start_time=_parse_time(row["start_time"]),
                end_time=_parse_time(row["end_time"]),
                semester=row["semester"],
                academic_year=row["academic_year"],
                target_course=row.get("target_course"),
                target_year_level=row.get("target_year_level"),
                early_leave_timeout_minutes=row.get("early_leave_timeout_minutes"),
                is_active=row.get("is_active", True),
            )
        )
    db.flush()
    return len(rows)


# ───────────────────────── delete helpers ─────────────────────────────────
#
# "Delete rows the Mac no longer has" implementation. Empty incoming set
# is treated as "delete nothing" for that table to avoid wiping the VPS
# on a Mac-side bug; the upsert helpers still run, so a genuine "Mac
# really has zero of these" state can be reached by deleting them
# manually on the VPS once.


def _delete_stale_schedules(db: Session, keep_ids: set[UUID]) -> int:
    if not keep_ids:
        return 0
    return (
        db.query(Schedule)
        .filter(Schedule.id.notin_(keep_ids))
        .delete(synchronize_session=False)
    )


def _delete_stale_rooms(db: Session, keep_ids: set[UUID]) -> int:
    if not keep_ids:
        return 0
    return (
        db.query(Room)
        .filter(Room.id.notin_(keep_ids))
        .delete(synchronize_session=False)
    )


def _delete_stale_users(db: Session, keep_ids: set[UUID]) -> int:
    if not keep_ids:
        return 0
    # Only touch faculty + admin rows. Any non-faculty/admin user that
    # somehow ended up on the VPS (legacy pre-split rows) is left alone.
    return (
        db.query(User)
        .filter(
            User.role.in_([UserRole.FACULTY, UserRole.ADMIN]),
            User.id.notin_(keep_ids),
        )
        .delete(synchronize_session=False)
    )


def _delete_stale_faculty_records(db: Session, keep_ids: set[str]) -> int:
    if not keep_ids:
        return 0
    return (
        db.query(FacultyRecord)
        .filter(FacultyRecord.faculty_id.notin_(keep_ids))
        .delete(synchronize_session=False)
    )


# ───────────────────────── route ──────────────────────────────────────────


@router.post("/upsert", response_model=SyncResponse, status_code=status.HTTP_200_OK)
def upsert_sync(
    payload: SyncRequest,
    x_sync_secret: str | None = Header(None, alias="X-Sync-Secret"),
    db: Session = Depends(get_db),
) -> SyncResponse:
    """Apply a full Mac-side snapshot of the four sync'd tables.

    Returns per-table upsert + delete counts so the sender can log them.
    """
    _verify_secret(x_sync_secret)

    # Safety guardrail: reject obviously-broken payloads before they
    # cascade-delete the VPS.
    if not payload.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Refusing to sync: payload contains zero users. "
                "The Mac always has at least one admin row — empty users "
                "list indicates a sender-side bug. Investigate before "
                "retrying."
            ),
        )

    # Pre-compute keep-id sets up-front so we can run helpers in any
    # order without re-walking the payload.
    keep_faculty_record_ids = {fr["faculty_id"] for fr in payload.faculty_records}
    keep_user_ids = {_parse_uuid(u["id"]) for u in payload.users}
    keep_room_ids = {_parse_uuid(r["id"]) for r in payload.rooms}
    keep_schedule_ids = {_parse_uuid(s["id"]) for s in payload.schedules}

    counts: dict[str, SyncTableCounts] = {}

    try:
        # Phase 1 — upsert in FK-parent → FK-child order.
        counts["faculty_records"] = SyncTableCounts(
            upserted=_upsert_faculty_records(db, payload.faculty_records),
            deleted=0,
        )
        counts["users"] = SyncTableCounts(
            upserted=_upsert_users(db, payload.users),
            deleted=0,
        )
        counts["rooms"] = SyncTableCounts(
            upserted=_upsert_rooms(db, payload.rooms),
            deleted=0,
        )
        counts["schedules"] = SyncTableCounts(
            upserted=_upsert_schedules(db, payload.schedules),
            deleted=0,
        )

        # Phase 2 — delete stale rows in reverse-FK order so children go
        # before parents.
        counts["schedules"].deleted = _delete_stale_schedules(db, keep_schedule_ids)
        counts["rooms"].deleted = _delete_stale_rooms(db, keep_room_ids)
        counts["users"].deleted = _delete_stale_users(db, keep_user_ids)
        counts["faculty_records"].deleted = _delete_stale_faculty_records(
            db, keep_faculty_record_ids
        )

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("[sync] receiver failed — rolled back transaction")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sync failed — see VPS logs for traceback",
        )

    received_at = datetime.utcnow().isoformat() + "Z"
    logger.info(
        "[sync] received from %s — counts=%s sent_at=%s",
        payload.source_host or "unknown",
        {k: f"+{v.upserted}/-{v.deleted}" for k, v in counts.items()},
        payload.sent_at,
    )

    return SyncResponse(
        received_at=received_at,
        source_host=payload.source_host,
        sent_at=payload.sent_at,
        counts=counts,
    )


@router.get("/health", status_code=status.HTTP_200_OK)
def sync_health(
    x_sync_secret: str | None = Header(None, alias="X-Sync-Secret"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Operator probe — counts the rows currently mirrored on the VPS.

    Useful from the Mac via curl to verify the secret + connectivity
    before flipping ENABLE_VPS_SYNC=true:

        curl -H "X-Sync-Secret: $VPS_SYNC_SECRET" \\
             https://<vps>/api/v1/sync/health
    """
    _verify_secret(x_sync_secret)
    return {
        "status": "ok",
        "tables": {
            "faculty_records": db.query(FacultyRecord).count(),
            "users_faculty_admin": (
                db.query(User)
                .filter(User.role.in_([UserRole.FACULTY, UserRole.ADMIN]))
                .count()
            ),
            "rooms": db.query(Room).count(),
            "schedules": db.query(Schedule).count(),
        },
    }
