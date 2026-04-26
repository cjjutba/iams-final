"""
Recognition Event Repository

Read-only data access for the recognition-evidence audit surface. Writes
are owned by ``app.services.evidence_writer`` which uses a direct SQL
INSERT for batching efficiency and is not routed through this repo.

All queries are cursor-paginated (descending ``created_at``) — an admin
can drift backwards through months of evidence without ever hitting the
``OFFSET N`` full-scan that breaks at 1 M rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from app.models.recognition_event import RecognitionEvent


class RecognitionRepository:
    """Read-only queries over recognition_events."""

    def __init__(self, db: Session):
        self.db = db

    # -- listing --------------------------------------------------------

    def list_events(
        self,
        *,
        schedule_id: Optional[str] = None,
        student_id: Optional[str] = None,
        matched: Optional[bool] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[RecognitionEvent]:
        """Cursor-paginated list.

        Cursor semantics: pass the last row's ``created_at`` + ``id`` from the
        previous page to continue. Composite cursor guards against ties in
        ``created_at`` (every batch flush has near-identical timestamps).
        """
        limit = max(1, min(200, int(limit)))
        q = self.db.query(RecognitionEvent).options(
            joinedload(RecognitionEvent.student),
            joinedload(RecognitionEvent.schedule),
        )

        if schedule_id:
            q = q.filter(RecognitionEvent.schedule_id == uuid.UUID(schedule_id))
        if student_id:
            q = q.filter(RecognitionEvent.student_id == uuid.UUID(student_id))
        if matched is not None:
            q = q.filter(RecognitionEvent.matched == matched)
        if since:
            q = q.filter(RecognitionEvent.created_at >= since)
        if until:
            q = q.filter(RecognitionEvent.created_at < until)

        if cursor_created_at and cursor_id:
            # (created_at, id) < cursor — strict keyset pagination.
            q = q.filter(
                (RecognitionEvent.created_at < cursor_created_at)
                | and_(
                    RecognitionEvent.created_at == cursor_created_at,
                    RecognitionEvent.id < uuid.UUID(cursor_id),
                )
            )

        q = q.order_by(
            desc(RecognitionEvent.created_at), desc(RecognitionEvent.id)
        ).limit(limit)
        return q.all()

    def get_by_id(self, event_id: str) -> Optional[RecognitionEvent]:
        try:
            eid = uuid.UUID(event_id)
        except ValueError:
            return None
        return (
            self.db.query(RecognitionEvent)
            .options(
                joinedload(RecognitionEvent.student),
                joinedload(RecognitionEvent.schedule),
            )
            .filter(RecognitionEvent.id == eid)
            .first()
        )

    # -- student summary -----------------------------------------------

    def summarize_for_student(
        self,
        *,
        student_id: str,
        schedule_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Aggregate counts + best/worst + histogram + timeline for one
        student, optionally narrowed to one schedule.

        Feeds the MatchEvidence section of the attendance details sheet:
        a summary of why this student was marked PRESENT / LATE /
        EARLY_LEAVE in plain numbers.
        """
        try:
            sid = uuid.UUID(student_id)
        except ValueError:
            return _empty_summary(student_id, schedule_id)

        base = self.db.query(RecognitionEvent).filter(
            RecognitionEvent.student_id == sid
        )
        if schedule_id:
            try:
                base = base.filter(
                    RecognitionEvent.schedule_id == uuid.UUID(schedule_id)
                )
            except ValueError:
                return _empty_summary(student_id, schedule_id)
        if since:
            base = base.filter(RecognitionEvent.created_at >= since)

        matched_q = base.filter(RecognitionEvent.matched.is_(True))
        missed_q = base.filter(RecognitionEvent.matched.is_(False))

        match_count = matched_q.count()
        miss_count = missed_q.count()

        best = matched_q.order_by(desc(RecognitionEvent.similarity)).first()
        worst = matched_q.order_by(RecognitionEvent.similarity.asc()).first()
        first = matched_q.order_by(RecognitionEvent.created_at.asc()).first()
        last = matched_q.order_by(desc(RecognitionEvent.created_at)).first()

        # 20-bucket histogram over 0..1 inclusive, matched + missed combined.
        # width_bucket is postgres-native.
        histogram_rows = (
            self.db.query(
                func.width_bucket(RecognitionEvent.similarity, 0.0, 1.0, 20).label(
                    "bucket"
                ),
                func.count().label("count"),
            )
            .filter(RecognitionEvent.student_id == sid)
            .group_by("bucket")
            .all()
        )
        histogram = [0] * 22  # buckets 0..21 (0 and 21 are out-of-range)
        for row in histogram_rows:
            idx = int(row.bucket or 0)
            if 0 <= idx < len(histogram):
                histogram[idx] = int(row.count)
        # Trim the boundary buckets to a clean 0..20 view for the UI.
        histogram = histogram[1:21]

        # Per-minute timeline for the active filter window.
        timeline_rows = (
            self.db.query(
                func.date_trunc("minute", RecognitionEvent.created_at).label("minute"),
                RecognitionEvent.matched,
                func.count().label("count"),
            )
            .filter(RecognitionEvent.student_id == sid)
            .group_by("minute", RecognitionEvent.matched)
            .order_by("minute")
            .all()
        )
        timeline: dict[str, dict[str, int]] = {}
        for row in timeline_rows:
            key = row.minute.isoformat() if row.minute else "unknown"
            bucket = timeline.setdefault(key, {"matches": 0, "misses": 0})
            if row.matched:
                bucket["matches"] = int(row.count)
            else:
                bucket["misses"] = int(row.count)
        timeline_flat = [
            {"minute": k, "matches": v["matches"], "misses": v["misses"]}
            for k, v in sorted(timeline.items())
        ]

        threshold_at_session = None
        if best:
            threshold_at_session = float(best.threshold_used)
        elif last:
            threshold_at_session = float(last.threshold_used)

        return {
            "student_id": student_id,
            "schedule_id": schedule_id,
            "match_count": match_count,
            "miss_count": miss_count,
            "best_match": _event_brief(best),
            "worst_accepted": _event_brief(worst),
            "first_match": _event_brief(first),
            "last_match": _event_brief(last),
            "histogram": histogram,
            "timeline": timeline_flat,
            "threshold_at_session": threshold_at_session,
        }


def _empty_summary(student_id: str, schedule_id: Optional[str]) -> dict[str, Any]:
    return {
        "student_id": student_id,
        "schedule_id": schedule_id,
        "match_count": 0,
        "miss_count": 0,
        "best_match": None,
        "worst_accepted": None,
        "first_match": None,
        "last_match": None,
        "histogram": [0] * 20,
        "timeline": [],
        "threshold_at_session": None,
    }


def _event_brief(e: Optional[RecognitionEvent]) -> Optional[dict[str, Any]]:
    if e is None:
        return None
    return {
        "event_id": str(e.id),
        "similarity": float(e.similarity),
        "timestamp": e.created_at.isoformat() if e.created_at else None,
    }
