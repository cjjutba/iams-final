"""
Face Repository

Data access layer for FaceRegistration and FaceEmbedding operations.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.face_embedding import FaceEmbedding
from app.models.face_registration import FaceRegistration
from app.utils.exceptions import DuplicateError, NotFoundError


class FaceRepository:
    """Repository for FaceRegistration CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, registration_id: str) -> FaceRegistration | None:
        """Get face registration by ID"""
        return self.db.query(FaceRegistration).filter(FaceRegistration.id == uuid.UUID(registration_id)).first()

    def get_by_user(self, user_id: str) -> FaceRegistration | None:
        """
        Get face registration for a user

        Args:
            user_id: User UUID

        Returns:
            FaceRegistration if found, None otherwise
        """
        return (
            self.db.query(FaceRegistration)
            .filter(FaceRegistration.user_id == uuid.UUID(user_id), FaceRegistration.is_active)
            .first()
        )

    def get_by_embedding_id(self, embedding_id: int) -> FaceRegistration | None:
        """
        Get face registration by FAISS embedding ID

        Args:
            embedding_id: FAISS index ID

        Returns:
            FaceRegistration if found, None otherwise
        """
        return (
            self.db.query(FaceRegistration)
            .filter(FaceRegistration.embedding_id == embedding_id, FaceRegistration.is_active)
            .first()
        )

    def get_active_embeddings(self) -> list[FaceRegistration]:
        """
        Get all active face registrations

        Used for rebuilding FAISS index

        Returns:
            List of active face registrations
        """
        return self.db.query(FaceRegistration).filter(FaceRegistration.is_active).all()

    def create(self, user_id: str, embedding_id: int, embedding_vector: bytes) -> FaceRegistration:
        """
        Create new face registration (commits immediately).

        Args:
            user_id: User UUID
            embedding_id: FAISS index ID
            embedding_vector: 512-dim embedding as bytes

        Returns:
            Created face registration

        Raises:
            DuplicateError: If user already has active registration
        """
        registration = self._create_no_commit(user_id, embedding_id, embedding_vector)
        self.db.commit()
        self.db.refresh(registration)
        return registration

    def _create_no_commit(self, user_id: str, embedding_id: int, embedding_vector: bytes) -> FaceRegistration:
        """
        Create new face registration without committing.

        Use when building a multi-row transaction (e.g. registration + embeddings).
        Caller is responsible for db.commit().

        Idempotent on the user_id UNIQUE constraint: purges ANY prior row for
        this user (active OR inactive) before inserting. Without this guard, a
        previously-soft-deleted registration (is_active=false) blocks the new
        INSERT with a `duplicate key value violates unique constraint` error.
        Cascade delete removes associated face_embeddings rows automatically.
        """
        uid = uuid.UUID(user_id)
        prior = (
            self.db.query(FaceRegistration)
            .filter(FaceRegistration.user_id == uid)
            .all()
        )
        for row in prior:
            self.db.delete(row)
        if prior:
            self.db.flush()  # ensure DELETEs happen before the INSERT in the same tx

        registration = FaceRegistration(
            user_id=uid, embedding_id=embedding_id, embedding_vector=embedding_vector
        )
        self.db.add(registration)
        self.db.flush()  # Assign PK (id) without committing
        return registration

    def deactivate(self, user_id: str) -> bool:
        """
        Deactivate face registration for a user

        Args:
            user_id: User UUID

        Returns:
            True if deactivated

        Raises:
            NotFoundError: If no active registration found
        """
        registration = self.get_by_user(user_id)
        if not registration:
            raise NotFoundError(f"No active face registration found for user: {user_id}")

        registration.is_active = False
        self.db.commit()
        return True

    def delete(self, registration_id: str) -> bool:
        """
        Permanently delete face registration

        Args:
            registration_id: Registration UUID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If registration not found
        """
        registration = self.get_by_id(registration_id)
        if not registration:
            raise NotFoundError(f"Face registration not found: {registration_id}")

        self.db.delete(registration)
        self.db.commit()
        return True

    def count_active(self) -> int:
        """Get count of active face registrations"""
        return self.db.query(FaceRegistration).filter(FaceRegistration.is_active).count()

    def count_all(self) -> int:
        """Get total count of face registrations"""
        return self.db.query(FaceRegistration).count()

    def count_inactive(self) -> int:
        """Get count of inactive face registrations"""
        return self.db.query(FaceRegistration).filter(FaceRegistration.is_active.is_(False)).count()

    # ------------------------------------------------------------------
    # Multi-embedding operations (FaceEmbedding table)
    # ------------------------------------------------------------------

    def create_embedding(
        self,
        registration_id: str,
        faiss_id: int,
        embedding_vector: bytes,
        angle_label: str | None = None,
        quality_score: float | None = None,
    ) -> FaceEmbedding:
        """Create a single FaceEmbedding row."""
        emb = FaceEmbedding(
            registration_id=uuid.UUID(registration_id),
            faiss_id=faiss_id,
            embedding_vector=embedding_vector,
            angle_label=angle_label,
            quality_score=quality_score,
        )
        self.db.add(emb)
        return emb

    def create_embeddings_batch(
        self,
        registration_id: str,
        entries: list[dict],
    ) -> list[FaceEmbedding]:
        """
        Batch-create FaceEmbedding rows.

        Args:
            registration_id: Parent FaceRegistration UUID.
            entries: List of dicts with keys: faiss_id, embedding_vector,
                     angle_label (optional), quality_score (optional).

        Returns:
            List of created FaceEmbedding instances (not yet committed).
        """
        reg_uuid = uuid.UUID(registration_id)
        rows = []
        for e in entries:
            row = FaceEmbedding(
                registration_id=reg_uuid,
                faiss_id=e["faiss_id"],
                embedding_vector=e["embedding_vector"],
                angle_label=e.get("angle_label"),
                quality_score=e.get("quality_score"),
            )
            self.db.add(row)
            rows.append(row)
        return rows

    def get_embeddings_by_registration(self, registration_id: str) -> list[FaceEmbedding]:
        """Get all embeddings for a registration."""
        return self.db.query(FaceEmbedding).filter(FaceEmbedding.registration_id == uuid.UUID(registration_id)).all()

    def get_all_active_embeddings(self) -> list[FaceEmbedding]:
        """
        Get all FaceEmbedding rows belonging to active registrations.

        Used for FAISS index rebuild with multi-embedding storage.
        """
        return (
            self.db.query(FaceEmbedding)
            .join(FaceRegistration, FaceEmbedding.registration_id == FaceRegistration.id)
            .filter(FaceRegistration.is_active)
            .all()
        )
