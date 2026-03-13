"""
Student Record Repository

Data access layer for the student_records reference table.
Used by AuthService to validate student IDs during registration.
"""

from sqlalchemy.orm import Session

from app.config import logger
from app.models.student_record import StudentRecord


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

    def exists(self, student_id: str) -> bool:
        """Return True if a record with this student_id exists."""
        return self.get_by_student_id(student_id) is not None
