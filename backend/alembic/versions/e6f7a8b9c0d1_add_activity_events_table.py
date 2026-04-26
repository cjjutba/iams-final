"""activity_events: unified discrete-event timeline for system activity page

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-24 00:30:00.000000

Why
---
The System Activity feature gives the admin portal one unified, queryable,
exportable event stream covering attendance state transitions, session
lifecycle, recognition-identity transitions (downsampled), admin audit,
and system health — for live tail, historical search, and thesis-defense
CSV/JSON export.

This migration creates the ``activity_events`` table and its five
composite supporting indexes. FK columns use ``ondelete="SET NULL"`` so
the audit trail survives PII deletion (essential for thesis
reproducibility). Drilldown ``ref_*`` columns reference retention-eligible
detail tables and therefore carry no FK at all.

Writes come from ``app.services.activity_service.emit_event()``; reads
from the new ``/api/v1/activity/events`` router.

Historical DBs (on-prem stack) were originally created via
``Base.metadata.create_all()`` and have no ``alembic_version`` row. For
those stacks the table is auto-created on next boot by ``init_db()``; the
migration is a no-op once stamped. Fresh clones run it normally.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create activity_events table + composite indexes."""
    op.create_table(
        "activity_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'info'"),
        ),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_room_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rooms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("camera_id", sa.String(length=64), nullable=True),
        # Drilldown refs — NO FK. Detail rows may be pruned by retention.
        sa.Column(
            "ref_attendance_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "ref_early_leave_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "ref_recognition_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Single-column indexes for primary filter columns.
    op.create_index(
        "ix_activity_events_event_type", "activity_events", ["event_type"]
    )
    op.create_index(
        "ix_activity_events_category", "activity_events", ["category"]
    )
    op.create_index(
        "ix_activity_events_subject_user_id",
        "activity_events",
        ["subject_user_id"],
    )
    op.create_index(
        "ix_activity_events_subject_schedule_id",
        "activity_events",
        ["subject_schedule_id"],
    )
    op.create_index(
        "ix_activity_events_created_at", "activity_events", ["created_at"]
    )

    # Composite indexes shaped to the admin page's most-likely filter combos.
    op.create_index(
        "ix_activity_category_created",
        "activity_events",
        ["category", "created_at"],
    )
    op.create_index(
        "ix_activity_type_created",
        "activity_events",
        ["event_type", "created_at"],
    )
    op.create_index(
        "ix_activity_schedule_created",
        "activity_events",
        ["subject_schedule_id", "created_at"],
    )
    op.create_index(
        "ix_activity_subject_created",
        "activity_events",
        ["subject_user_id", "created_at"],
    )
    op.create_index(
        "ix_activity_severity_created",
        "activity_events",
        ["severity", "created_at"],
    )


def downgrade() -> None:
    """Drop activity_events table + all indexes."""
    op.drop_index(
        "ix_activity_severity_created", table_name="activity_events"
    )
    op.drop_index(
        "ix_activity_subject_created", table_name="activity_events"
    )
    op.drop_index(
        "ix_activity_schedule_created", table_name="activity_events"
    )
    op.drop_index("ix_activity_type_created", table_name="activity_events")
    op.drop_index(
        "ix_activity_category_created", table_name="activity_events"
    )
    op.drop_index(
        "ix_activity_events_created_at", table_name="activity_events"
    )
    op.drop_index(
        "ix_activity_events_subject_schedule_id",
        table_name="activity_events",
    )
    op.drop_index(
        "ix_activity_events_subject_user_id", table_name="activity_events"
    )
    op.drop_index("ix_activity_events_category", table_name="activity_events")
    op.drop_index(
        "ix_activity_events_event_type", table_name="activity_events"
    )
    op.drop_table("activity_events")
