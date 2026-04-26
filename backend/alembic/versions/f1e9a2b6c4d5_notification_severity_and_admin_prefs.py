"""notification severity column and admin preference keys

Revision ID: f1e9a2b6c4d5
Revises: d6e7f8a9b0c1, e6f7a8b9c0d1
Create Date: 2026-04-25 00:00:00.000000

Why
---
Phase 1 of the notifications system overhaul. Adds:

* ``notifications.severity`` — short string column (info/success/warn/
  error/critical) plus an index. Drives the admin sidebar's
  "unread critical" badge and frontend toast styling.
* ``notification_preferences.{camera_alerts, ml_health_alerts,
  security_alerts, audit_alerts, schedule_conflict_alerts, face_alerts,
  daily_health_summary}`` — admin-facing preference flags. ``audit_alerts``
  and ``daily_health_summary`` are opt-in (default ``false``) because
  peer-admin audit chatter and daily digests are noisy in small teams.

This revision also merges the two pre-existing alembic heads
(``d6e7f8a9b0c1`` and ``e6f7a8b9c0d1``) so the chain has a single tip
again.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1e9a2b6c4d5"
down_revision: Union[str, Sequence[str], None] = ("d6e7f8a9b0c1", "e6f7a8b9c0d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── notifications.severity ─────────────────────────────────────
    op.add_column(
        "notifications",
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default="info",
        ),
    )
    op.create_index(
        "ix_notifications_severity",
        "notifications",
        ["severity"],
    )

    # ── notification_preferences.* (admin-facing flags) ────────────
    op.add_column(
        "notification_preferences",
        sa.Column(
            "camera_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "ml_health_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "security_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "audit_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "schedule_conflict_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "face_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "daily_health_summary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "daily_health_summary")
    op.drop_column("notification_preferences", "face_alerts")
    op.drop_column("notification_preferences", "schedule_conflict_alerts")
    op.drop_column("notification_preferences", "audit_alerts")
    op.drop_column("notification_preferences", "security_alerts")
    op.drop_column("notification_preferences", "ml_health_alerts")
    op.drop_column("notification_preferences", "camera_alerts")
    op.drop_index("ix_notifications_severity", table_name="notifications")
    op.drop_column("notifications", "severity")
