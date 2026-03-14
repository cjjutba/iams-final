"""
Student Record Repository

Data access layer for the student_records reference table.
Used by AuthService to validate student IDs during registration.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import logger
from app.models.student_record import StudentRecord
from app.models.user import User
from app.utils.exceptions import NotFoundError


class StudentRecordRepository:
    """Repository for student_records reference table."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_student_id(self, student_id: str) -> StudentRecord | None:
        """
        Look up a student record by the school-issued student ID.

        Returns None if not found (student is not enrolled in the school).
        """
        return self.db.query(StudentRecord).filter(StudentRecord.student_id == student_id.strip().upper()).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[StudentRecord]:
        """Return a paginated list of all student records."""
        return self.db.query(StudentRecord).filter(StudentRecord.is_active).offset(skip).limit(limit).all()

    def get_all_with_status(self, skip: int = 0, limit: int = 1000) -> list[dict]:
        """Return all student records with app registration status."""
        from app.models.face_registration import FaceRegistration

        results = (
            self.db.query(
                StudentRecord,
                func.coalesce(User.id, None).label("user_id"),
                func.count(FaceRegistration.id).label("face_count"),
            )
            .outerjoin(User, User.student_id == StudentRecord.student_id)
            .outerjoin(FaceRegistration, (FaceRegistration.user_id == User.id) & (FaceRegistration.is_active == True))
            .group_by(StudentRecord.student_id, User.id)
            .order_by(StudentRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        enriched = []
        for record, user_id, face_count in results:
            enriched.append({
                "record": record,
                "user_id": str(user_id) if user_id else None,
                "is_registered": user_id is not None,
                "has_face_registered": face_count > 0,
            })
        return enriched

    def count(self) -> int:
        """Return total number of active student records."""
        return self.db.query(StudentRecord).filter(StudentRecord.is_active).count()

    def create(self, data: dict) -> StudentRecord:
        """Insert a new student record (used by seed scripts)."""
        record = StudentRecord(**data)
        self.db.add(record)
        self.db.flush()
        logger.info(f"Created student record: {record.student_id}")
        return record

    def update(self, student_id: str, update_data: dict) -> StudentRecord:
        """Update a student record."""
        record = self.get_by_student_id(student_id)
        if not record:
            raise NotFoundError(f"Student record not found: {student_id}")
        for key, value in update_data.items():
            if hasattr(record, key) and value is not None:
                setattr(record, key, value)
        self.db.flush()
        return record

    def deactivate(self, student_id: str) -> bool:
        """Soft-delete a student record."""
        record = self.get_by_student_id(student_id)
        if not record:
            raise NotFoundError(f"Student record not found: {student_id}")
        record.is_active = False
        self.db.flush()
        return True

    def exists(self, student_id: str) -> bool:
        """Return True if a record with this student_id exists."""
        return self.get_by_student_id(student_id) is not None
