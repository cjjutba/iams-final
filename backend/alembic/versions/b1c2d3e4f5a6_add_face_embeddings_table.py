"""add face_embeddings table

Revision ID: b1c2d3e4f5a6
Revises: 86d63351d3e9
Create Date: 2026-03-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: str = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'face_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('registration_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('faiss_id', sa.Integer(), nullable=False),
        sa.Column('embedding_vector', sa.LargeBinary(), nullable=False),
        sa.Column('angle_label', sa.String(length=20), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['registration_id'], ['face_registrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_face_embeddings_registration_id', 'face_embeddings', ['registration_id'])
    op.create_index('ix_face_embeddings_faiss_id', 'face_embeddings', ['faiss_id'])


def downgrade() -> None:
    op.drop_index('ix_face_embeddings_faiss_id', table_name='face_embeddings')
    op.drop_index('ix_face_embeddings_registration_id', table_name='face_embeddings')
    op.drop_table('face_embeddings')
