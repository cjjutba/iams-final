"""face_embeddings: add nullable image_storage_key for persisted registration images

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-23 00:00:00.000000

Why
---
Until now the face registration flow read the 3-5 uploaded angle images into
memory, extracted ArcFace embeddings, and dropped the raw bytes on the floor.
That was fine until the admin portal grew a "face comparison" sheet on the
live-feed page (`admin/src/components/live-feed/TrackDetailSheet.tsx`) — we
want to visibly tie a detected face to the specific angles the student
registered with.

This migration adds a single nullable column. Pre-existing registrations stay
valid with a null storage key; the admin UI simply renders metadata-only
tiles for them (graceful fallback decision — see
`memory/lessons.md` 2026-04-23 on nullable columns beating forced
re-enrollment). New registrations populated by
`backend/app/services/face_service.py.register_face` write a relative path
like ``registrations/<user_uuid>/<angle>_<uuid12>.jpg`` under the existing
`face_uploads_onprem` volume (``/app/data/uploads/faces``).

The column is read by the admin-only endpoints in
`backend/app/routers/face.py`:
- ``GET /api/v1/face/registrations/{user_id}`` (metadata + URL index)
- ``GET /api/v1/face/registrations/{user_id}/images/{angle_label}`` (bytes)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable image_storage_key column."""
    op.add_column(
        "face_embeddings",
        sa.Column("image_storage_key", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Drop the image_storage_key column (JPEGs on disk are orphaned)."""
    op.drop_column("face_embeddings", "image_storage_key")
