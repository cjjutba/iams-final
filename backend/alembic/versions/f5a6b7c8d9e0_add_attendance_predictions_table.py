"""add attendance predictions table

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-03-04 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: str = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

risk_level_enum = postgresql.ENUM(
    'critical', 'high', 'moderate', 'low',
    name='risklevel', create_type=False
)


def upgrade() -> None:
    risk_level_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'attendance_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('schedules.id'), nullable=False, index=True),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('predicted_rate', sa.Float(), nullable=False),
        sa.Column('trend', sa.String(length=20), nullable=False, server_default='stable'),
        sa.Column('risk_level', risk_level_enum, nullable=False),
        sa.Column('actual_rate', sa.Float(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('attendance_predictions')
    risk_level_enum.drop(op.get_bind(), checkfirst=True)
