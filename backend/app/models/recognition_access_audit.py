"""
Recognition Access Audit Model

Phase 5 of the recognition-evidence plan. Every time an admin fetches a
live-crop or registered-crop JPEG from the ``/api/v1/recognitions/*``
router, a row is inserted here with the viewer, target event, crop kind,
and request metadata.

Exists to answer the question a school registrar gets when a parent asks
"who has looked at my child's face in this system?" — a legally defensible
access log with per-view attribution.

See docs/plans/2026-04-22-recognition-evidence/DESIGN.md §5.5.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RecognitionAccessAudit(Base):
    """One row per crop-fetch request.

    Indexed by viewer_user_id + viewed_at so "who viewed what, in order"
    queries stay fast. Retained for 3 years regardless of
    ``RECOGNITION_*_RETENTION_DAYS`` (legal requirement, not a tuning knob).

    Attributes:
        id: BIGSERIAL — append-only log; sequential scan performance wins
            over UUID for this access pattern.
        viewer_user_id: The admin making the request.
        event_id: The recognition_event being viewed. CASCADE on delete so
            purging evidence (Phase 5.6 right-to-delete) wipes the audit
            trail for those rows too.
        crop_kind: ``'live'`` or ``'registered'``.
        viewed_at: Server clock at request time.
        ip: Best-effort client IP (nginx-forwarded, falls back to direct).
        user_agent: For audit context; not used in queries.
    """

    __tablename__ = "recognition_access_audit"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    viewer_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recognition_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    crop_kind = Column(String(16), nullable=False)
    viewed_at = Column(
        DateTime, default=lambda: datetime.now(), nullable=False
    )
    ip = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    viewer = relationship("User")
    event = relationship("RecognitionEvent")

    __table_args__ = (
        CheckConstraint(
            "crop_kind IN ('live', 'registered')",
            name="ck_recognition_access_crop_kind",
        ),
        Index(
            "ix_recognition_access_viewer_time",
            "viewer_user_id",
            "viewed_at",
        ),
        Index(
            "ix_recognition_access_event",
            "event_id",
            "viewed_at",
        ),
    )

    def __repr__(self):
        return (
            f"<RecognitionAccessAudit(viewer={self.viewer_user_id}, "
            f"event={self.event_id}, kind={self.crop_kind})>"
        )


# Generate uuid stub for use in SQL default if ever needed; the id is
# BIGSERIAL so this is purely for code-level consistency.
_ = uuid.uuid4  # keep import lint-clean
