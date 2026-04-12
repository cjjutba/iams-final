"""
FacultyRecord Model

Reference table representing the school's official faculty registry.
This is NOT the users table — it is the source-of-truth for faculty
employed by the university. Faculty accounts in the users table are
pre-seeded by admins referencing this table.

When real school data is available, this table is populated via import.
For development/pilot testing, it is populated with mock data.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String

from app.database import Base


class FacultyRecord(Base):
    """Official faculty record from the university's human resources system."""

    __tablename__ = "faculty_records"

    # Primary key: the school-issued faculty ID (e.g., "FAC-001")
    faculty_id = Column(String(50), primary_key=True, nullable=False)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    # Official school email
    email = Column(String(255), nullable=False, unique=True)

    department = Column(String(100), nullable=True)  # e.g., "Computer Engineering"

    # Whether this faculty member is currently active
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now())

    def __repr__(self) -> str:
        return f"<FacultyRecord faculty_id={self.faculty_id!r} name={self.first_name!r} {self.last_name!r}>"
