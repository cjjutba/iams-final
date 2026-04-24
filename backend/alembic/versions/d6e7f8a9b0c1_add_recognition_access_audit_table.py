"""recognition_access_audit: per-view audit log of crop fetches (Phase 5)

Revision ID: d6e7f8a9b0c1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-24 01:00:00.000000

Why
---
Phase 5 of the Recognition Evidence plan
(docs/plans/2026-04-22-recognition-evidence/DESIGN.md §5.5).

Every time an admin fetches a recognition-evidence crop (live or
registered) the router must insert one row here. This answers the legal
"who has viewed my child's biometric data" question that motivated the
whole enterprise-hardening phase. Retention is 3 years (not configurable
— compliance requirement, not a tuning knob).

Production DBs are built by ``Base.metadata.create_all()`` — same pattern
as the earlier recognition_events migration. Fresh clones that actually
stamp/upgrade get the table via Alembic; existing stacks pick it up from
``init_db()`` on boot.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recognition_access_audit",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "viewer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recognition_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("crop_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "viewed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "crop_kind IN ('live', 'registered')",
            name="ck_recognition_access_crop_kind",
        ),
    )
    op.create_index(
        "ix_recognition_access_viewer_time",
        "recognition_access_audit",
        ["viewer_user_id", "viewed_at"],
    )
    op.create_index(
        "ix_recognition_access_event",
        "recognition_access_audit",
        ["event_id", "viewed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recognition_access_event", table_name="recognition_access_audit"
    )
    op.drop_index(
        "ix_recognition_access_viewer_time", table_name="recognition_access_audit"
    )
    op.drop_table("recognition_access_audit")
