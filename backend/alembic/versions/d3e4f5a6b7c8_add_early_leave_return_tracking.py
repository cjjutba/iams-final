"""add early leave return tracking and severity

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-03-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: str = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('early_leave_events', sa.Column('returned', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('early_leave_events', sa.Column('returned_at', sa.DateTime(), nullable=True))
    op.add_column('early_leave_events', sa.Column('absence_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('early_leave_events', sa.Column('context_severity', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('early_leave_events', 'context_severity')
    op.drop_column('early_leave_events', 'absence_duration_seconds')
    op.drop_column('early_leave_events', 'returned_at')
    op.drop_column('early_leave_events', 'returned')
