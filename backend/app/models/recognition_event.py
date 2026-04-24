"""
Recognition Event Model

Every FAISS decision produced by the realtime recognition pipeline — match
or miss — is persisted as a ``recognition_events`` row plus a pair of JPEG
crops (live probe + the registered angle it matched against). This is the
evidence trail that powers the admin-portal Face Verification card on the
student detail page, the MatchEvidence section of the attendance-detail
sheet, and the ``/recognitions`` cross-schedule audit page.

The write path is asynchronous and lossy-by-design: on back-pressure the
evidence writer drops events rather than block the real-time pipeline.
Every row snapshots the threshold + model name that were in effect at
decision time so historical records remain auditable even after
``RECOGNITION_THRESHOLD`` or ``INSIGHTFACE_MODEL`` is retuned.

See docs/plans/2026-04-22-recognition-evidence/DESIGN.md §Data model.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RecognitionEvent(Base):
    """
    One FAISS decision on one tracked face in one frame.

    Attributes:
        id: UUID primary key. Also used to name the crop JPEGs on disk —
            ``<id>-live.jpg`` and ``<id>-reg.jpg`` — so filename uniqueness
            is guaranteed without coordinating with the DB worker.
        schedule_id: Schedule the decision was made under. CASCADE so that
            removing a schedule wipes its evidence trail automatically.
        student_id: The matched user (or NULL for a miss / ambiguous
            match). ON DELETE SET NULL so a student's row deletion does
            not orphan the event rows, but ``face_service`` also cascades
            crop deletion explicitly for right-to-delete compliance.
        track_id: ByteTrack track id the event was produced for.
        camera_id: Short camera handle (e.g. ``eb226``).
        frame_idx: Frame counter local to the pipeline run.
        similarity: Raw FAISS inner-product score (cosine similarity on
            L2-normalised 512-dim embeddings, so in [-1, 1] in theory but
            in practice [0, 1]).
        threshold_used: Snapshot of ``settings.RECOGNITION_THRESHOLD`` at
            event time. Keeps historical decisions auditable across
            threshold retuning.
        matched: True iff ``similarity >= threshold_used AND NOT is_ambiguous``.
        is_ambiguous: Top-1/top-2 margin was below
            ``settings.RECOGNITION_MARGIN``.
        det_score: SCRFD detection confidence for the source face.
        embedding_norm: L2 norm of the probe embedding pre-normalisation;
            a QA signal that lets us catch mis-calibrated crops.
        bbox: ``{x1, y1, x2, y2}`` in source-frame pixels, from the aligned
            crop that went into ArcFace.
        live_crop_ref: Relative path under ``RECOGNITION_EVIDENCE_CROP_ROOT``
            for the live probe JPEG.
        registered_crop_ref: Relative path to the registered-angle JPEG
            that was the top-1 match, or NULL for a miss.
        model_name: Which InsightFace pack produced the embedding (e.g.
            ``buffalo_l``). Same auditability reason as ``threshold_used``.
        created_at: Server clock at write time.
    """

    __tablename__ = "recognition_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    track_id = Column(Integer, nullable=False)
    camera_id = Column(String(50), nullable=False)
    frame_idx = Column(Integer, nullable=False)
    similarity = Column(Float, nullable=False)
    threshold_used = Column(Float, nullable=False)
    matched = Column(Boolean, nullable=False)
    is_ambiguous = Column(Boolean, nullable=False, default=False)
    det_score = Column(Float, nullable=False)
    embedding_norm = Column(Float, nullable=False)
    bbox = Column(JSONB, nullable=False)
    live_crop_ref = Column(Text, nullable=False)
    registered_crop_ref = Column(Text, nullable=True)
    model_name = Column(String(64), nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(), nullable=False
    )

    # Relationships — lazy by default; the admin REST endpoints eagerly load
    # only when they need the student/schedule for display.
    schedule = relationship("Schedule")
    student = relationship("User")

    __table_args__ = (
        Index(
            "ix_recognition_events_schedule_created",
            "schedule_id",
            "created_at",
        ),
        Index(
            "ix_recognition_events_student_created",
            "student_id",
            "created_at",
        ),
        Index(
            "ix_recognition_events_matched",
            "schedule_id",
            "matched",
            "created_at",
        ),
        Index(
            "ix_recognition_events_track",
            "schedule_id",
            "track_id",
            "created_at",
        ),
    )

    def __repr__(self):
        return (
            f"<RecognitionEvent(id={self.id}, schedule_id={self.schedule_id}, "
            f"student_id={self.student_id}, similarity={self.similarity:.3f}, "
            f"matched={self.matched})>"
        )
