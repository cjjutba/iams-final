"""
Face Embedding Model

Stores individual face embeddings for multi-angle registration.
Each FaceRegistration can have multiple FaceEmbeddings (one per angle).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import backref, relationship

from app.database import Base


class FaceEmbedding(Base):
    """
    Individual face embedding from a registration image.

    Instead of averaging N embeddings into 1, we store each embedding
    separately so FAISS can match against the best angle. This improves
    recognition accuracy for profile/angled views.

    Attributes:
        id: UUID primary key
        registration_id: FK to face_registrations
        faiss_id: Position in FAISS index
        embedding_vector: 512-dim ArcFace embedding as bytes
        angle_label: Optional label ('center', 'left', 'right', 'up', 'down')
        quality_score: Overall quality score from face_quality.assess_quality
        created_at: Timestamp
    """

    __tablename__ = "face_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("face_registrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    faiss_id = Column(Integer, nullable=False)
    embedding_vector = Column(LargeBinary, nullable=False)
    angle_label = Column(String(20), nullable=True)
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    registration = relationship(
        "FaceRegistration",
        backref=backref("embeddings", cascade="all, delete-orphan", passive_deletes=True),
    )

    __table_args__ = (
        Index("ix_face_embeddings_registration_id", "registration_id"),
        Index("ix_face_embeddings_faiss_id", "faiss_id"),
    )

    def __repr__(self):
        return (
            f"<FaceEmbedding(id={self.id}, registration_id={self.registration_id}, "
            f"faiss_id={self.faiss_id}, angle={self.angle_label})>"
        )
