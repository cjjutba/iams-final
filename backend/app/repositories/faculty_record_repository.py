"""
Faculty Record Repository

Data access layer for the faculty_records reference table.
"""

from sqlalchemy.orm import Session

from app.config import logger
from app.models.faculty_record import FacultyRecord


class FacultyRecordRepository:
    """Repository for faculty_records reference table."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_faculty_id(self, faculty_id: str) -> FacultyRecord | None:
        """Look up a faculty record by the school-issued faculty ID."""
        return self.db.query(FacultyRecord).filter(FacultyRecord.faculty_id == faculty_id.strip().upper()).first()

    def get_by_email(self, email: str) -> FacultyRecord | None:
        """Look up a faculty record by email."""
        return self.db.query(FacultyRecord).filter(FacultyRecord.email == email.strip().lower()).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[FacultyRecord]:
        """Return a paginated list of all active faculty records."""
        return self.db.query(FacultyRecord).filter(FacultyRecord.is_active).offset(skip).limit(limit).all()

    def create(self, data: dict) -> FacultyRecord:
        """Insert a new faculty record (used by seed scripts)."""
        record = FacultyRecord(**data)
        self.db.add(record)
        self.db.flush()
        logger.info(f"Created faculty record: {record.faculty_id}")
        return record

    def exists(self, faculty_id: str) -> bool:
        """Return True if a record with this faculty_id exists."""
        return self.get_by_faculty_id(faculty_id) is not None
