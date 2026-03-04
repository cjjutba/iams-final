"""add notification preferences table

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-03-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a6b7c8d9e0f1'
down_revision: str = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_preferences',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('early_leave_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('anomaly_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('attendance_confirmation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('low_attendance_warning', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('daily_digest', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('weekly_digest', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('low_attendance_threshold', sa.Float(), nullable=False, server_default='75.0'),
    )


def downgrade() -> None:
    op.drop_table('notification_preferences')
