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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.student_record import StudentRecord
from app.models.faculty_record import FacultyRecord
from app.config import logger


# ---------------------------------------------------------------------------
# Mock student registry (10 students, BSCPE, JRMSU)
# Format: (student_id, first_name, last_name, email, course, year_level, section)
# ---------------------------------------------------------------------------
MOCK_STUDENTS = [
    # 4th year students
    ("21-A-02177", "Christian Jerald", "Jutba",      "cjjutbaofficial@gmail.com",        "BSCPE", 4, "A"),
    ("21-A-12345", "Juan",             "Dela Cruz",  "juan.delacruz@jrmsu.edu.ph",        "BSCPE", 4, "A"),
    ("21-B-55555", "Sofia",            "Torres",     "sofia.torres@jrmsu.edu.ph",         "BSCPE", 4, "B"),
    # 3rd year students
    ("22-A-54321", "Maria",            "Santos",     "maria.santos@jrmsu.edu.ph",         "BSCPE", 3, "A"),
    ("22-A-67890", "Jose",             "Reyes",      "jose.reyes@jrmsu.edu.ph",           "BSCPE", 3, "A"),
    ("22-B-66666", "Miguel",           "Flores",     "miguel.flores@jrmsu.edu.ph",        "BSCPE", 3, "B"),
    # 2nd year students
    ("23-A-11111", "Ana",              "Garcia",     "ana.garcia@jrmsu.edu.ph",           "BSCPE", 2, "A"),
    ("23-A-22222", "Pedro",            "Gonzales",   "pedro.gonzales@jrmsu.edu.ph",       "BSCPE", 2, "A"),
    # 1st year students
    ("24-A-33333", "Maria",            "Rodriguez",  "maria.rodriguez@jrmsu.edu.ph",      "BSCPE", 1, "A"),
    ("24-A-44444", "Carlo",            "Mendoza",    "carlo.mendoza@jrmsu.edu.ph",        "BSCPE", 1, "B"),
]

# ---------------------------------------------------------------------------
# Mock faculty registry
# ---------------------------------------------------------------------------
MOCK_FACULTY = [
    ("FAC-001", "Faculty",  "User",    "faculty@gmail.com",              "Computer Engineering"),
    ("FAC-002", "Roberto",  "Aquino",  "roberto.aquino@jrmsu.edu.ph",    "Computer Engineering"),
    ("FAC-003", "Lourdes",  "Bautista","lourdes.bautista@jrmsu.edu.ph",  "Computer Engineering"),
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

        for student_id, first_name, last_name, email, course, year_level, section in MOCK_STUDENTS:
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
                    is_active=True,
                )
                db.add(record)
                print(f"  ADD   {student_id} — {first_name} {last_name} (Year {year_level}-{section})")
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
        print(f"\nTotal active student IDs for registration:")
        for student_id, first_name, last_name, *_ in MOCK_STUDENTS:
            print(f"  {student_id}  ({first_name} {last_name})")

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
