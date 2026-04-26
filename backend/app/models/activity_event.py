"""
Activity Event Model

Every discrete domain event worth narrating — attendance state transitions,
session lifecycle, recognition-identity transitions (downsampled, NOT every
frame), admin audit, and system health — is persisted as an
``activity_events`` row. This is the row-ful, immutable evidence trail that
backs the admin-portal System Activity page (live tail + historical search
+ CSV/JSON export for thesis defense).

Why this table and not a view-of-unions over existing tables:
  * ``attendance_records.status`` mutates in place (PRESENT → LATE →
    EARLY_LEAVE on the same row), so the timeline cannot be reconstructed
    from the current-state row.
  * ``presence_logs`` is per-60-s per-student noise — unusable as a feed.
  * A view recomputes on every read, so future service-logic changes
    would silently shift historical rows. Thesis evidence must be
    immutable.
  * The real-time WebSocket fanout requires a write-time emission anyway;
    once that exists the row comes essentially free.

Write path:
  * Every write goes through ``app.services.activity_service.emit_event()``
    which shares the caller's DB transaction (``db.flush()`` by default)
    so the event row is atomic with its underlying state change. Standalone
    callers pass ``autocommit=True``.
  * After the DB write, the helper publishes the event JSON to the Redis
    subchannel ``{REDIS_WS_CHANNEL}:activity:global`` so the existing
    WebSocket subscriber loop in ``app.routers.websocket`` can fan it out
    to connected clients.
  * Recognition events are downsampled AT THE EMIT SITE: the pipeline's
    existing ``_recognized_captured: set[(user_id, track_id)]`` gate gives
    us exactly one RECOGNITION_MATCH per tracker identity transition.

FK cascade: all ``actor_id`` / ``subject_*_id`` columns use
``ondelete="SET NULL"`` so the activity log outlives PII deletion —
essential for thesis reproducibility. The ``ref_*`` columns reference
retention-eligible detail tables and therefore carry NO foreign key.

See docs/plans/… (unwritten yet; tracked in
memory/lessons.md entry 2026-04-24 "System Activity timeline").
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ActivityEvent(Base):
    """One discrete domain event in the system timeline.

    Attributes:
        id: UUID primary key.
        event_type: Canonical event type string (e.g. ``MARKED_PRESENT``).
            Defined in :class:`app.services.activity_service.EventType`.
        category: Coarse grouping for UI filter chips. One of
            ``attendance | session | recognition | system | audit``.
        severity: ``info | success | warn | error`` — drives the UI's
            severity-rail colour.
        actor_type: ``system | user | pipeline``. Who triggered the event.
        actor_id: Nullable FK to ``users.id`` — the admin/faculty/student
            who caused the event, if any. SET NULL on user delete so the
            audit trail survives.
        subject_user_id: Nullable FK to ``users.id`` — the student/user
            the event is ABOUT (check-in subject, deleted-user target).
        subject_schedule_id: Nullable FK to ``schedules.id``.
        subject_room_id: Nullable FK to ``rooms.id``.
        camera_id: Short camera handle (e.g. ``eb226``) for system events.
        ref_attendance_id / ref_early_leave_id / ref_recognition_event_id:
            Drilldown references to detail tables. NO FK constraint —
            detail rows may be pruned by retention policy while the
            activity log is preserved long-term.
        summary: Human-readable one-line description for list rendering
            (e.g. "Juan Dela Cruz marked PRESENT for CS101").
        payload: Optional structured JSONB for the event-detail sheet and
            CSV/JSON export. Discipline: IDs not full nested objects, keep
            ≤~2 KB per event.
        created_at: Timezone-aware server clock at emit time.
    """

    __tablename__ = "activity_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_type = Column(String(64), nullable=False, index=True)
    category = Column(String(32), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="info")
    actor_type = Column(String(16), nullable=False)

    # All FKs SET NULL on delete — activity log must outlive PII deletion.
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_room_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
    )
    camera_id = Column(String(64), nullable=True)

    # Drilldown refs — NO FK constraints (detail rows may be purged by
    # retention). The admin page resolves these lazily.
    ref_attendance_id = Column(UUID(as_uuid=True), nullable=True)
    ref_early_leave_id = Column(UUID(as_uuid=True), nullable=True)
    ref_recognition_event_id = Column(UUID(as_uuid=True), nullable=True)

    summary = Column(String(500), nullable=False)
    payload = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
        index=True,
    )

    # Relationships — lazy, used by joined loaders in ActivityRepository
    # when the admin list view needs actor/subject names resolved.
    actor = relationship("User", foreign_keys=[actor_id])
    subject_user = relationship("User", foreign_keys=[subject_user_id])
    schedule = relationship("Schedule", foreign_keys=[subject_schedule_id])

    __table_args__ = (
        # Composite indexes shaped to the admin page's most-likely filters.
        Index("ix_activity_category_created", "category", "created_at"),
        Index("ix_activity_type_created", "event_type", "created_at"),
        Index(
            "ix_activity_schedule_created",
            "subject_schedule_id",
            "created_at",
        ),
        Index(
            "ix_activity_subject_created",
            "subject_user_id",
            "created_at",
        ),
        Index("ix_activity_severity_created", "severity", "created_at"),
    )

    def __repr__(self):
        return (
            f"<ActivityEvent(id={self.id}, type={self.event_type}, "
            f"category={self.category}, severity={self.severity})>"
        )
