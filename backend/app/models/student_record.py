"""
StudentRecord Model

Reference table representing the school's official student registry.
This is NOT the users table — it is the source-of-truth for who is
enrolled in the university. Students must exist here before they can
self-register in the IAMS mobile app.

When real school data is available, this table is populated via import.
For development/pilot testing, it is populated with mock data.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from app.database import Base


class StudentRecord(Base):
    """Official student record from the university's student information system."""

    __tablename__ = "student_records"

    # Primary key: the school-issued student ID (e.g., "21-A-02177")
    student_id = Column(String(50), primary_key=True, nullable=False)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    # Official school email (e.g., firstname.lastname@jrmsu.edu.ph)
    email = Column(String(255), nullable=True)

    # Academic info
    course = Column(String(100), nullable=True)   # e.g., "BSCPE"
    year_level = Column(Integer, nullable=True)   # 1–5
    section = Column(String(10), nullable=True)   # e.g., "A", "B"

    # Whether this student is currently enrolled/active
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<StudentRecord student_id={self.student_id!r} "
            f"name={self.first_name!r} {self.last_name!r}>"
        )
