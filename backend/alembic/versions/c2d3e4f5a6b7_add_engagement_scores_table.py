"""add engagement_scores table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-04 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: str = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'engagement_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('attendance_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consistency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('punctuality_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sustained_presence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence_avg', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attendance_id'], ['attendance_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attendance_id'),
    )
    op.create_index('ix_engagement_scores_attendance_id', 'engagement_scores', ['attendance_id'])


def downgrade() -> None:
    op.drop_index('ix_engagement_scores_attendance_id', table_name='engagement_scores')
    op.drop_table('engagement_scores')
