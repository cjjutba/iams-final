"""add early_leave_timeout_minutes to schedules

Revision ID: a7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-04-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: str = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'schedules',
        sa.Column('early_leave_timeout_minutes', sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        'ck_early_leave_timeout_range',
        'schedules',
        'early_leave_timeout_minutes >= 1 AND early_leave_timeout_minutes <= 15',
    )


def downgrade() -> None:
    op.drop_constraint('ck_early_leave_timeout_range', 'schedules', type_='check')
    op.drop_column('schedules', 'early_leave_timeout_minutes')
