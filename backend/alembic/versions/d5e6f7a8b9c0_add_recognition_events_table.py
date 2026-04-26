"""recognition_events: capture every FAISS decision with paired crops + score

Revision ID: d5e6f7a8b9c0
Revises: c9d0e1f2a3b4
Create Date: 2026-04-24 00:00:00.000000

Why
---
Phase 1 of the Recognition Evidence plan
(docs/plans/2026-04-22-recognition-evidence/DESIGN.md). Today every FAISS
match/miss is thrown away the instant the pipeline moves on — there is no
way for an admin to audit why a student was marked PRESENT, and no data
to empirically justify the ``RECOGNITION_THRESHOLD`` choice for the thesis
defense.

This migration creates the ``recognition_events`` table and its four
supporting indexes. Schedule / student deletion cascade rules are set up
so the evidence trail lives exactly as long as the entities it refers to.

The table is written to by ``app.services.evidence_writer`` (a bounded
asyncio queue + batched INSERT worker) at real-time pipeline rate. Read
by the new ``/api/v1/recognitions`` admin router, the student detail
Recent Detections list, the attendance-detail MatchEvidence section, and
the cross-schedule audit page.

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
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create recognition_events table + indexes."""
    op.create_table(
        "recognition_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.String(length=50), nullable=False),
        sa.Column("frame_idx", sa.Integer(), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("threshold_used", sa.Float(), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column(
            "is_ambiguous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("det_score", sa.Float(), nullable=False),
        sa.Column("embedding_norm", sa.Float(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("live_crop_ref", sa.Text(), nullable=False),
        sa.Column("registered_crop_ref", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_recognition_events_schedule_created",
        "recognition_events",
        ["schedule_id", "created_at"],
    )
    op.create_index(
        "ix_recognition_events_student_created",
        "recognition_events",
        ["student_id", "created_at"],
    )
    op.create_index(
        "ix_recognition_events_matched",
        "recognition_events",
        ["schedule_id", "matched", "created_at"],
    )
    op.create_index(
        "ix_recognition_events_track",
        "recognition_events",
        ["schedule_id", "track_id", "created_at"],
    )


def downgrade() -> None:
    """Drop recognition_events table (crop JPEGs on disk are orphaned)."""
    op.drop_index("ix_recognition_events_track", table_name="recognition_events")
    op.drop_index("ix_recognition_events_matched", table_name="recognition_events")
    op.drop_index(
        "ix_recognition_events_student_created", table_name="recognition_events"
    )
    op.drop_index(
        "ix_recognition_events_schedule_created", table_name="recognition_events"
    )
    op.drop_table("recognition_events")
