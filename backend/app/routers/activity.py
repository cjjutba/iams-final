"""
System Activity Router

Admin-only REST surface over ``activity_events``:

- ``GET /api/v1/activity/events``              — cursor-paginated list
- ``GET /api/v1/activity/events/stats``        — live dashboard counters
- ``GET /api/v1/activity/events/export.csv``   — streaming CSV of filtered set
- ``GET /api/v1/activity/events/export.json``  — streaming NDJSON (full payloads)
- ``GET /api/v1/activity/events/{id}``         — single event

All endpoints require an admin-authenticated user. Mounted only when
``ENABLE_ACTIVITY_ROUTES`` is true (disabled on VPS thin profile).

The REST surface is a peer of the real-time WebSocket feed at
``/api/v1/ws/events`` — both read from the same ``activity_events`` table,
both apply the same filter semantics, both use admin-only auth.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.activity_repository import ActivityRepository
from app.schemas.activity import (
    ActivityCategoryStats,
    ActivityEventResponse,
    ActivityListResponse,
    ActivitySeverityStats,
    ActivityStatsResponse,
)
from app.utils.dependencies import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# -- helpers --------------------------------------------------------------


def _event_to_response(row) -> ActivityEventResponse:
    actor_name = None
    if row.actor is not None:
        first = getattr(row.actor, "first_name", None) or ""
        last = getattr(row.actor, "last_name", None) or ""
        actor_name = f"{first} {last}".strip() or None

    subject_user_name = None
    if row.subject_user is not None:
        first = getattr(row.subject_user, "first_name", None) or ""
        last = getattr(row.subject_user, "last_name", None) or ""
        subject_user_name = f"{first} {last}".strip() or None

    subject_schedule_subject = None
    if row.schedule is not None:
        subject_schedule_subject = getattr(row.schedule, "subject_code", None)

    def _id(x):
        return str(x) if x is not None else None

    return ActivityEventResponse(
        event_id=str(row.id),
        event_type=row.event_type,
        category=row.category,
        severity=row.severity,
        actor_type=row.actor_type,
        actor_id=_id(row.actor_id),
        actor_name=actor_name,
        subject_user_id=_id(row.subject_user_id),
        subject_user_name=subject_user_name,
        subject_schedule_id=_id(row.subject_schedule_id),
        subject_schedule_subject=subject_schedule_subject,
        subject_room_id=_id(row.subject_room_id),
        camera_id=row.camera_id,
        ref_attendance_id=_id(row.ref_attendance_id),
        ref_early_leave_id=_id(row.ref_early_leave_id),
        ref_recognition_event_id=_id(row.ref_recognition_event_id),
        summary=row.summary,
        payload=row.payload,
        created_at=row.created_at,
    )


def _parse_cursor(
    cursor: Optional[str],
) -> tuple[Optional[datetime], Optional[str]]:
    """Cursor format is ``<iso>|<uuid>`` produced by the server on the
    previous page. Both halves required. Silently ignores malformed
    cursors — the client gets the first page instead of a 500.
    """
    if not cursor:
        return None, None
    try:
        iso, raw_id = cursor.split("|", 1)
        created_at = datetime.fromisoformat(iso)
        uuid.UUID(raw_id)  # validate
        return created_at, raw_id
    except Exception:
        return None, None


def _build_cursor(row) -> str:
    return f"{row.created_at.isoformat()}|{row.id}"


def _parse_multi(value: Optional[str]) -> Optional[list[str]]:
    """Parse a comma-separated multi-value query param.

    FastAPI supports repeated query params but clients often find CSV
    simpler. Accept either — if the value contains a comma, split it;
    otherwise treat as a single value.
    """
    if not value:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None


# -- endpoints ------------------------------------------------------------


@router.get("/events", response_model=ActivityListResponse)
def list_events(
    event_type: Optional[str] = Query(
        default=None,
        description="CSV list of event types to include (e.g. MARKED_PRESENT,MARKED_LATE)",
    ),
    category: Optional[str] = Query(
        default=None,
        description="CSV list of categories: attendance,session,recognition,system,audit",
    ),
    severity: Optional[str] = Query(
        default=None,
        description="CSV list of severities: info,success,warn,error",
    ),
    schedule_id: Optional[str] = Query(default=None),
    student_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ActivityListResponse:
    """Cursor-paginated listing.

    Pass the returned ``next_cursor`` to advance. All filters combine with
    AND semantics across fields; within multi-value fields (event_type,
    category, severity), values are OR.
    """
    repo = ActivityRepository(db)
    cursor_created, cursor_id = _parse_cursor(cursor)

    rows = repo.list_events(
        event_types=_parse_multi(event_type),
        categories=_parse_multi(category),
        severities=_parse_multi(severity),
        schedule_id=schedule_id,
        student_id=student_id,
        actor_id=actor_id,
        since=since,
        until=until,
        cursor_created_at=cursor_created,
        cursor_id=cursor_id,
        limit=limit,
    )
    items = [_event_to_response(r) for r in rows]
    next_cursor = _build_cursor(rows[-1]) if len(rows) == limit else None
    return ActivityListResponse(items=items, next_cursor=next_cursor)


@router.get("/events/stats", response_model=ActivityStatsResponse)
def get_stats(
    window_minutes: int = Query(default=15, ge=1, le=1440),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ActivityStatsResponse:
    """Rolling-window counters for the live dashboard strip."""
    repo = ActivityRepository(db)
    stats = repo.compute_stats(window_minutes=window_minutes)
    return ActivityStatsResponse(
        window_minutes=stats["window_minutes"],
        window_start=stats["window_start"],
        window_end=stats["window_end"],
        total_events=stats["total_events"],
        events_per_minute=stats["events_per_minute"],
        by_category=ActivityCategoryStats(**stats["by_category"]),
        by_severity=ActivitySeverityStats(**stats["by_severity"]),
        active_session_count=stats["active_session_count"],
    )


@router.get("/events/export.csv")
def export_csv(
    event_type: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    schedule_id: Optional[str] = Query(default=None),
    student_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streaming CSV of the filtered set.

    Walks the keyset cursor in a generator so large exports don't
    materialise the whole set in memory.
    """
    repo = ActivityRepository(db)
    types = _parse_multi(event_type)
    cats = _parse_multi(category)
    sevs = _parse_multi(severity)

    def generate() -> Iterable[bytes]:
        header = io.StringIO()
        writer = csv.writer(header)
        writer.writerow(
            [
                "event_id",
                "created_at",
                "event_type",
                "category",
                "severity",
                "actor_type",
                "actor_id",
                "actor_name",
                "subject_user_id",
                "subject_user_name",
                "subject_schedule_id",
                "subject_schedule_subject",
                "camera_id",
                "summary",
            ]
        )
        yield header.getvalue().encode()

        cursor_created: Optional[datetime] = None
        cursor_id: Optional[str] = None
        while True:
            rows = repo.list_events(
                event_types=types,
                categories=cats,
                severities=sevs,
                schedule_id=schedule_id,
                student_id=student_id,
                actor_id=actor_id,
                since=since,
                until=until,
                cursor_created_at=cursor_created,
                cursor_id=cursor_id,
                limit=200,
            )
            if not rows:
                return
            buf = io.StringIO()
            w = csv.writer(buf)
            for r in rows:
                actor_name = ""
                if r.actor is not None:
                    actor_name = f"{getattr(r.actor, 'first_name', '')} {getattr(r.actor, 'last_name', '')}".strip()
                subj_name = ""
                if r.subject_user is not None:
                    subj_name = f"{getattr(r.subject_user, 'first_name', '')} {getattr(r.subject_user, 'last_name', '')}".strip()
                subj_subject = ""
                if r.schedule is not None:
                    subj_subject = getattr(r.schedule, "subject_code", "") or ""
                w.writerow(
                    [
                        str(r.id),
                        r.created_at.isoformat() if r.created_at else "",
                        r.event_type,
                        r.category,
                        r.severity,
                        r.actor_type,
                        str(r.actor_id) if r.actor_id else "",
                        actor_name,
                        str(r.subject_user_id) if r.subject_user_id else "",
                        subj_name,
                        str(r.subject_schedule_id) if r.subject_schedule_id else "",
                        subj_subject,
                        r.camera_id or "",
                        r.summary,
                    ]
                )
            yield buf.getvalue().encode()
            if len(rows) < 200:
                return
            cursor_created = rows[-1].created_at
            cursor_id = str(rows[-1].id)

    filename = f"activity-{datetime.now():%Y%m%d-%H%M%S}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/events/export.json")
def export_ndjson(
    event_type: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    schedule_id: Optional[str] = Query(default=None),
    student_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streaming NDJSON of the filtered set — preserves full payloads for
    reproducibility.

    Each line is a self-contained JSON object; concatenation is not valid
    JSON but is trivially parsed line-by-line.
    """
    repo = ActivityRepository(db)
    types = _parse_multi(event_type)
    cats = _parse_multi(category)
    sevs = _parse_multi(severity)

    def generate() -> Iterable[bytes]:
        cursor_created: Optional[datetime] = None
        cursor_id: Optional[str] = None
        while True:
            rows = repo.list_events(
                event_types=types,
                categories=cats,
                severities=sevs,
                schedule_id=schedule_id,
                student_id=student_id,
                actor_id=actor_id,
                since=since,
                until=until,
                cursor_created_at=cursor_created,
                cursor_id=cursor_id,
                limit=200,
            )
            if not rows:
                return
            out = io.StringIO()
            for r in rows:
                obj: dict[str, Any] = {
                    "event_id": str(r.id),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "event_type": r.event_type,
                    "category": r.category,
                    "severity": r.severity,
                    "actor_type": r.actor_type,
                    "actor_id": str(r.actor_id) if r.actor_id else None,
                    "subject_user_id": str(r.subject_user_id) if r.subject_user_id else None,
                    "subject_schedule_id": str(r.subject_schedule_id) if r.subject_schedule_id else None,
                    "subject_room_id": str(r.subject_room_id) if r.subject_room_id else None,
                    "camera_id": r.camera_id,
                    "ref_attendance_id": str(r.ref_attendance_id) if r.ref_attendance_id else None,
                    "ref_early_leave_id": str(r.ref_early_leave_id) if r.ref_early_leave_id else None,
                    "ref_recognition_event_id": (
                        str(r.ref_recognition_event_id) if r.ref_recognition_event_id else None
                    ),
                    "summary": r.summary,
                    "payload": r.payload,
                }
                out.write(json.dumps(obj, default=str))
                out.write("\n")
            yield out.getvalue().encode()
            if len(rows) < 200:
                return
            cursor_created = rows[-1].created_at
            cursor_id = str(rows[-1].id)

    filename = f"activity-{datetime.now():%Y%m%d-%H%M%S}.ndjson"
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/events/{event_id}", response_model=ActivityEventResponse)
def get_event(
    event_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ActivityEventResponse:
    repo = ActivityRepository(db)
    row = repo.get_by_id(event_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return _event_to_response(row)
