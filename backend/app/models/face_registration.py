"""
Face Registration Model

Links users to their face embeddings in FAISS index.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FaceRegistration(Base):
    """
    Face registration model

    Stores the mapping between users and their FAISS embedding IDs.
    Also stores the embedding vector for index rebuilding.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to users table (unique - one face per user)
        embedding_id: ID in FAISS index
        embedding_vector: The 512-dim embedding (stored as bytes for rebuild)
        registered_at: Timestamp of registration
        is_active: Whether this registration is active
    """

    __tablename__ = "face_registrations"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    # FAISS mapping
    embedding_id = Column(Integer, nullable=False)  # Index in FAISS
    embedding_vector = Column(LargeBinary, nullable=False)  # 512-dim vector as bytes (for rebuild)

    # Timestamps
    registered_at = Column(DateTime, default=lambda: datetime.now(), nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="face_registration")

    def __repr__(self):
        return f"<FaceRegistration(id={self.id}, user_id={self.user_id}, embedding_id={self.embedding_id})>"
