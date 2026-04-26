"""
Activity Event schemas.

Request/response shapes for the ``/api/v1/activity`` admin router. See
memory/lessons.md 2026-04-24 for design rationale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ActivityEventResponse(BaseModel):
    """One row in the System Activity timeline."""

    event_id: str
    event_type: str
    category: str
    severity: str
    actor_type: str

    actor_id: Optional[str] = None
    actor_name: Optional[str] = None

    subject_user_id: Optional[str] = None
    subject_user_name: Optional[str] = None
    # Distinct from ``subject_user_id`` (the user UUID) — this is the
    # human-facing student record number (e.g. "JR-2024-001234"). Used by
    # the admin sidebar's "View student" drilldown so the URL points at
    # the route param the student-record-detail page actually accepts.
    subject_user_student_id: Optional[str] = None

    subject_schedule_id: Optional[str] = None
    subject_schedule_subject: Optional[str] = None

    subject_room_id: Optional[str] = None
    camera_id: Optional[str] = None

    # Drilldown refs (no FK) — may be null if the underlying detail row
    # has been purged by retention, but the activity row is preserved.
    ref_attendance_id: Optional[str] = None
    ref_early_leave_id: Optional[str] = None
    ref_recognition_event_id: Optional[str] = None

    summary: str
    payload: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    items: list[ActivityEventResponse]
    next_cursor: Optional[str] = None  # "<iso_created_at>|<uuid>" or None


class ActivityCategoryStats(BaseModel):
    """Per-category counters for the live dashboard strip."""

    attendance: int = 0
    session: int = 0
    recognition: int = 0
    system: int = 0
    audit: int = 0


class ActivitySeverityStats(BaseModel):
    """Per-severity counters for the live dashboard strip."""

    info: int = 0
    success: int = 0
    warn: int = 0
    error: int = 0


class ActivityStatsResponse(BaseModel):
    """Live counters over a rolling window (default last 15 minutes).

    Used by the top strip of the /activity page.
    """

    window_minutes: int
    window_start: datetime
    window_end: datetime
    total_events: int
    events_per_minute: float
    by_category: ActivityCategoryStats
    by_severity: ActivitySeverityStats
    active_session_count: int  # Schedules with a SESSION_STARTED_* event and no SESSION_ENDED_* inside the window
