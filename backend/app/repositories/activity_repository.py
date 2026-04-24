"""
Activity Event Repository

Read-only data access for the System Activity admin surface. Writes are
owned by ``app.services.activity_service.emit_event()`` (which shares the
caller's DB transaction) and are not routed through this repo.

All queries are cursor-paginated on ``(created_at, id)`` descending — an
admin can drift backwards through months of history without hitting the
``OFFSET N`` full-scan that breaks at 1 M rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, desc, distinct, func
from sqlalchemy.orm import Session, joinedload

from app.models.activity_event import ActivityEvent


class ActivityRepository:
    """Read-only queries over ``activity_events``."""

    def __init__(self, db: Session):
        self.db = db

    # -- listing --------------------------------------------------------

    def list_events(
        self,
        *,
        event_types: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        severities: Optional[list[str]] = None,
        schedule_id: Optional[str] = None,
        student_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ActivityEvent]:
        """Cursor-paginated list with multi-value filter support.

        ``event_types``, ``categories``, ``severities`` are OR within their
        set, AND across sets.
        """
        limit = max(1, min(200, int(limit)))
        q = self.db.query(ActivityEvent).options(
            joinedload(ActivityEvent.actor),
            joinedload(ActivityEvent.subject_user),
            joinedload(ActivityEvent.schedule),
        )

        if event_types:
            q = q.filter(ActivityEvent.event_type.in_(event_types))
        if categories:
            q = q.filter(ActivityEvent.category.in_(categories))
        if severities:
            q = q.filter(ActivityEvent.severity.in_(severities))
        if schedule_id:
            try:
                q = q.filter(
                    ActivityEvent.subject_schedule_id == uuid.UUID(schedule_id)
                )
            except ValueError:
                return []
        if student_id:
            try:
                q = q.filter(
                    ActivityEvent.subject_user_id == uuid.UUID(student_id)
                )
            except ValueError:
                return []
        if actor_id:
            try:
                q = q.filter(ActivityEvent.actor_id == uuid.UUID(actor_id))
            except ValueError:
                return []
        if since:
            q = q.filter(ActivityEvent.created_at >= since)
        if until:
            q = q.filter(ActivityEvent.created_at < until)

        if cursor_created_at and cursor_id:
            # Strict keyset pagination: (created_at, id) < cursor.
            # Guards against ties in created_at when emit bursts share a ms.
            try:
                cursor_uuid = uuid.UUID(cursor_id)
            except ValueError:
                cursor_uuid = None
            if cursor_uuid is not None:
                q = q.filter(
                    (ActivityEvent.created_at < cursor_created_at)
                    | and_(
                        ActivityEvent.created_at == cursor_created_at,
                        ActivityEvent.id < cursor_uuid,
                    )
                )

        q = q.order_by(
            desc(ActivityEvent.created_at), desc(ActivityEvent.id)
        ).limit(limit)
        return q.all()

    def get_by_id(self, event_id: str) -> Optional[ActivityEvent]:
        try:
            eid = uuid.UUID(event_id)
        except ValueError:
            return None
        return (
            self.db.query(ActivityEvent)
            .options(
                joinedload(ActivityEvent.actor),
                joinedload(ActivityEvent.subject_user),
                joinedload(ActivityEvent.schedule),
            )
            .filter(ActivityEvent.id == eid)
            .first()
        )

    # -- stats ----------------------------------------------------------

    def compute_stats(self, *, window_minutes: int = 15) -> dict[str, Any]:
        """Rolling-window aggregates for the live dashboard strip."""
        window_minutes = max(1, min(1440, int(window_minutes)))
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)

        base = self.db.query(ActivityEvent).filter(
            ActivityEvent.created_at >= window_start
        )

        total = base.count()

        by_category_rows = (
            self.db.query(
                ActivityEvent.category, func.count().label("count")
            )
            .filter(ActivityEvent.created_at >= window_start)
            .group_by(ActivityEvent.category)
            .all()
        )
        by_category = {
            "attendance": 0,
            "session": 0,
            "recognition": 0,
            "system": 0,
            "audit": 0,
        }
        for row in by_category_rows:
            if row.category in by_category:
                by_category[row.category] = int(row.count)

        by_severity_rows = (
            self.db.query(
                ActivityEvent.severity, func.count().label("count")
            )
            .filter(ActivityEvent.created_at >= window_start)
            .group_by(ActivityEvent.severity)
            .all()
        )
        by_severity = {"info": 0, "success": 0, "warn": 0, "error": 0}
        for row in by_severity_rows:
            if row.severity in by_severity:
                by_severity[row.severity] = int(row.count)

        # Active sessions inside the window = schedules with a
        # SESSION_STARTED_* event minus those with a matching SESSION_ENDED_*.
        # Cheap approximation — an admin-ops metric, not accounting.
        started_schedule_ids = {
            row[0]
            for row in self.db.query(
                distinct(ActivityEvent.subject_schedule_id)
            )
            .filter(
                ActivityEvent.created_at >= window_start,
                ActivityEvent.event_type.in_(
                    ["SESSION_STARTED_AUTO", "SESSION_STARTED_MANUAL"]
                ),
                ActivityEvent.subject_schedule_id.isnot(None),
            )
            .all()
            if row[0] is not None
        }
        ended_schedule_ids = {
            row[0]
            for row in self.db.query(
                distinct(ActivityEvent.subject_schedule_id)
            )
            .filter(
                ActivityEvent.created_at >= window_start,
                ActivityEvent.event_type.in_(
                    ["SESSION_ENDED_AUTO", "SESSION_ENDED_MANUAL"]
                ),
                ActivityEvent.subject_schedule_id.isnot(None),
            )
            .all()
            if row[0] is not None
        }
        active_session_count = len(started_schedule_ids - ended_schedule_ids)

        events_per_minute = round(total / window_minutes, 2) if total else 0.0

        return {
            "window_minutes": window_minutes,
            "window_start": window_start,
            "window_end": now,
            "total_events": total,
            "events_per_minute": events_per_minute,
            "by_category": by_category,
            "by_severity": by_severity,
            "active_session_count": active_session_count,
        }
