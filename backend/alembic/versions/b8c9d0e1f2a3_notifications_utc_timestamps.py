"""notifications: convert created_at / read_at to TIMESTAMPTZ (UTC)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-18 12:00:00.000000

Why
---
Previously the columns were naive ``TIMESTAMP WITHOUT TIME ZONE``. The model
wrote ``datetime.now()`` (naive local-time), so mobile clients had to guess
whether the timestamp was UTC or the backend host's local time. On any host
that isn't UTC (or on a laptop during dev) this produced "Just now" labels
for hours- or days-old notifications because the relative-time formatter saw
a future instant.

This migration converts both timestamp columns to ``TIMESTAMP WITH TIME ZONE``
and reinterprets existing naive values as UTC (no wall-clock shift), matching
the model's new ``DateTime(timezone=True)`` + ``datetime.now(timezone.utc)``
default.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # AT TIME ZONE 'UTC' tells Postgres: "these naive values were already UTC,
    # just attach the offset." It does NOT shift wall-clock time.
    op.execute(
        "ALTER TABLE notifications "
        "ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE notifications "
        "ALTER COLUMN read_at TYPE TIMESTAMP WITH TIME ZONE "
        "USING read_at AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    """Downgrade schema — drop the timezone, keeping the UTC wall-clock."""
    op.execute(
        "ALTER TABLE notifications "
        "ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE notifications "
        "ALTER COLUMN read_at TYPE TIMESTAMP WITHOUT TIME ZONE "
        "USING read_at AT TIME ZONE 'UTC'"
    )
