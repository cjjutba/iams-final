"""add_target_course_year_to_schedules

Revision ID: a1b2c3d4e5f6
Revises: 7bf7e45a61d8
Create Date: 2026-02-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7bf7e45a61d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedules', sa.Column('target_course', sa.String(100), nullable=True))
    op.add_column('schedules', sa.Column('target_year_level', sa.Integer(), nullable=True))
    op.create_index('idx_schedule_target', 'schedules', ['target_course', 'target_year_level'])


def downgrade() -> None:
    op.drop_index('idx_schedule_target', table_name='schedules')
    op.drop_column('schedules', 'target_year_level')
    op.drop_column('schedules', 'target_course')
