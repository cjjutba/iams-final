"""add_birthdate_contact_to_student_records

Revision ID: 7bf7e45a61d8
Revises: 53db1ce6f3d0
Create Date: 2026-02-12 08:02:55.045255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bf7e45a61d8'
down_revision: Union[str, Sequence[str], None] = '53db1ce6f3d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add birthdate and contact_number columns to student_records
    op.add_column('student_records', sa.Column('birthdate', sa.Date(), nullable=True))
    op.add_column('student_records', sa.Column('contact_number', sa.String(20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove birthdate and contact_number columns
    op.drop_column('student_records', 'contact_number')
    op.drop_column('student_records', 'birthdate')
