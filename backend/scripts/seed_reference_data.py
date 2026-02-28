"""
Reference Data Seed Script

Populates student_records and faculty_records tables with mock data
that simulates the school's Student Information System (SIS).

This data is used to validate student IDs during self-registration:
  1. Student enters their Student ID on the registration screen
  2. Backend checks student_records table
  3. If found, official name/course/year/section/email are pre-filled
  4. Student confirms details, sets password, proceeds to face registration

In production: Replace mock data by importing a real CSV/API export from
the school's SIS. The registration validation logic stays the same.

Run from backend directory:
    python -m scripts.seed_reference_data

This script is idempotent -- skips records that already exist.
"""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.student_record import StudentRecord
from app.models.faculty_record import FacultyRecord
from app.config import logger


# ---------------------------------------------------------------------------
# Student registry for testing (single real user for thesis demo)
# Format: (student_id, first_name, last_name, email, course, year_level, section, birthdate, contact_number)
# ---------------------------------------------------------------------------
MOCK_STUDENTS = [
    ("21-A-02177", "Christian Jerald", "Jutba", "cjjutbaofficial@gmail.com", "BSCPE", 4, "A", date(2003, 1, 13), "09764556948"),
]

# ---------------------------------------------------------------------------
# Mock faculty registry (only 1 for testing)
# ---------------------------------------------------------------------------
MOCK_FACULTY = [
    ("FAC-001", "Faculty",  "User",    "faculty@gmail.com",              "Computer Engineering"),
]


def seed_reference_data():
    """Seed student_records and faculty_records tables."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Reference Data")
        print("=" * 60)

        # ---- Student Records ----
        print("\n[1/2] Seeding student records...")
        added = 0
        skipped = 0

        for student_id, first_name, last_name, email, course, year_level, section, birthdate, contact_number in MOCK_STUDENTS:
            existing = db.query(StudentRecord).filter(
                StudentRecord.student_id == student_id
            ).first()

            if existing:
                print(f"  SKIP  {student_id} — already exists")
                skipped += 1
            else:
                record = StudentRecord(
                    student_id=student_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    course=course,
                    year_level=year_level,
                    section=section,
                    birthdate=birthdate,
                    contact_number=contact_number,
                    is_active=True,
                )
                db.add(record)
                print(f"  ADD   {student_id} — {first_name} {last_name} (Year {year_level}-{section}) DOB: {birthdate}")
                added += 1

        # ---- Faculty Records ----
        print("\n[2/2] Seeding faculty records...")
        fac_added = 0
        fac_skipped = 0

        for faculty_id, first_name, last_name, email, department in MOCK_FACULTY:
            existing = db.query(FacultyRecord).filter(
                FacultyRecord.faculty_id == faculty_id
            ).first()

            if existing:
                print(f"  SKIP  {faculty_id} — already exists")
                fac_skipped += 1
            else:
                record = FacultyRecord(
                    faculty_id=faculty_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    department=department,
                    is_active=True,
                )
                db.add(record)
                print(f"  ADD   {faculty_id} — {first_name} {last_name}")
                fac_added += 1

        db.commit()
        logger.info("Reference data seeded successfully")

        print("\n" + "=" * 60)
        print("REFERENCE DATA SEED COMPLETE")
        print("=" * 60)
        print(f"\nStudent Records: {added} added, {skipped} skipped")
        print(f"Faculty Records: {fac_added} added, {fac_skipped} skipped")
        print(f"\nAvailable student IDs for registration:")
        for student_id, first_name, last_name, *rest in MOCK_STUDENTS:
            birthdate = rest[5]
            print(f"  {student_id}  ({first_name} {last_name})  DOB: {birthdate}")

    except Exception as e:
        db.rollback()
        logger.error(f"Reference data seed failed: {e}")
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_reference_data()
