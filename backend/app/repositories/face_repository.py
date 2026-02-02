"""
Face Repository

Data access layer for FaceRegistration operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.face_registration import FaceRegistration
from app.utils.exceptions import NotFoundError, DuplicateError


class FaceRepository:
    """Repository for FaceRegistration CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, registration_id: str) -> Optional[FaceRegistration]:
        """Get face registration by ID"""
        return self.db.query(FaceRegistration).filter(FaceRegistration.id == registration_id).first()

    def get_by_user(self, user_id: str) -> Optional[FaceRegistration]:
        """
        Get face registration for a user

        Args:
            user_id: User UUID

        Returns:
            FaceRegistration if found, None otherwise
        """
        return self.db.query(FaceRegistration).filter(
            FaceRegistration.user_id == user_id,
            FaceRegistration.is_active == True
        ).first()

    def get_by_embedding_id(self, embedding_id: int) -> Optional[FaceRegistration]:
        """
        Get face registration by FAISS embedding ID

        Args:
            embedding_id: FAISS index ID

        Returns:
            FaceRegistration if found, None otherwise
        """
        return self.db.query(FaceRegistration).filter(
            FaceRegistration.embedding_id == embedding_id,
            FaceRegistration.is_active == True
        ).first()

    def get_active_embeddings(self) -> List[FaceRegistration]:
        """
        Get all active face registrations

        Used for rebuilding FAISS index

        Returns:
            List of active face registrations
        """
        return self.db.query(FaceRegistration).filter(
            FaceRegistration.is_active == True
        ).all()

    def create(self, user_id: str, embedding_id: int, embedding_vector: bytes) -> FaceRegistration:
        """
        Create new face registration

        Args:
            user_id: User UUID
            embedding_id: FAISS index ID
            embedding_vector: 512-dim embedding as bytes

        Returns:
            Created face registration

        Raises:
            DuplicateError: If user already has active registration
        """
        # Check if user already has active registration
        existing = self.get_by_user(user_id)
        if existing:
            raise DuplicateError(f"User already has active face registration: {user_id}")

        registration = FaceRegistration(
            user_id=user_id,
            embedding_id=embedding_id,
            embedding_vector=embedding_vector
        )
        self.db.add(registration)
        self.db.commit()
        self.db.refresh(registration)
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
        return self.db.query(FaceRegistration).filter(FaceRegistration.is_active == True).count()
