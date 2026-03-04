"""add attendance anomalies table

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-03-04 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: str = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Create enum type
anomaly_type_enum = postgresql.ENUM(
    'sudden_absence', 'proxy_suspect', 'pattern_break', 'low_confidence',
    name='anomalytype', create_type=False
)


def upgrade() -> None:
    # Create enum type first
    anomaly_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'attendance_anomalies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('schedules.id'), nullable=True, index=True),
        sa.Column('anomaly_type', anomaly_type_enum, nullable=False, index=True),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('attendance_anomalies')
    anomaly_type_enum.drop(op.get_bind(), checkfirst=True)
