"""add realtime tracking columns to attendance_records and presence_logs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add total_present_seconds to attendance_records for time-based presence tracking
    op.add_column(
        'attendance_records',
        sa.Column('total_present_seconds', sa.Float(), nullable=False, server_default='0.0')
    )

    # Add track_id to presence_logs for ByteTrack correlation
    op.add_column(
        'presence_logs',
        sa.Column('track_id', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('presence_logs', 'track_id')
    op.drop_column('attendance_records', 'total_present_seconds')
