"""
Reference Data Seed Script

Populates student_records and faculty_records tables from real school data
parsed from docs/data/ListofStudents_All-thesis-purposes.md.

Also includes a test student (Christian Jerald Jutba) for development/demo.

This data is used to validate student IDs during self-registration:
  1. Student enters their Student ID on the registration screen
  2. Backend checks student_records table
  3. If found, official name/course/year/section/email are pre-filled
  4. Student confirms details, sets password, proceeds to face registration

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
from scripts.seed_school_data import (
    parse_students_from_md,
    deduplicate_students,
    parse_name,
    parse_date_str,
    normalize_student_id,
    infer_year_level,
    infer_section,
    MARKDOWN_PATH,
)


# ---------------------------------------------------------------------------
# Test student (always included for development/demo)
# ---------------------------------------------------------------------------
TEST_STUDENT = {
    "student_id": "21-A-02177",
    "first_name": "Christian Jerald",
    "last_name": "Jutba",
    "email": "cjjutbaofficial@gmail.com",
    "course": "BSCPE",
    "year_level": 4,
    "section": "A",
    "birthdate": date(2003, 1, 13),
    "contact_number": "09764556948",
}

# ---------------------------------------------------------------------------
# Faculty records: default test account + 3 real JRMSU instructors
# ---------------------------------------------------------------------------
MOCK_FACULTY = [
    ("FAC-001", "Faculty", "User", "faculty@gmail.com", "Computer Engineering"),
    ("FAC-002", "Ryan", "Elumba", "ryan.elumba@jrmsu.edu.ph", "Computer Engineering"),
    ("FAC-003", "Maricon Denber", "Gahisan", "maricon.gahisan@jrmsu.edu.ph", "Computer Engineering"),
    ("FAC-004", "Troy", "Lasco", "troy.lasco@jrmsu.edu.ph", "Computer Engineering"),
]


def seed_reference_data():
    """Seed student_records and faculty_records from real school data."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Reference Data")
        print("=" * 60)

        # ---- Parse students from markdown ----
        print("\n[1/2] Seeding student records from school data...")

        if MARKDOWN_PATH.exists():
            raw = parse_students_from_md(MARKDOWN_PATH)
            students = deduplicate_students(raw)
            print(f"  Parsed {len(students)} unique students from markdown")
        else:
            students = []
            print(f"  WARNING: Markdown file not found: {MARKDOWN_PATH}")

        added = 0
        skipped = 0
        used_ids: set[str] = set()
        pending_counter = 1

        # Pre-load existing student IDs for idempotency
        existing_ids = {
            r.student_id for r in db.query(StudentRecord.student_id).all()
        }

        for entry in students:
            first_name, middle_name, last_name = parse_name(entry["name"])
            email = entry["email"].lower().strip() if entry["email"] else None
            birthdate = parse_date_str(entry["birthdate"])
            raw_sid = normalize_student_id(entry["student_id"])
            course = "BSECE" if entry["program"] == "ECE" else "BSCPE"

            # Assign student ID
            if raw_sid and raw_sid not in used_ids:
                student_id = raw_sid
            elif raw_sid and raw_sid in used_ids:
                student_id = f"PENDING-{pending_counter:04d}"
                pending_counter += 1
            else:
                student_id = f"PENDING-{pending_counter:04d}"
                pending_counter += 1

            used_ids.add(student_id)
            year_level = infer_year_level(student_id)
            section = infer_section(student_id)

            # Idempotency check
            if student_id in existing_ids:
                skipped += 1
                continue

            # For PENDING IDs, also check by name
            if student_id.startswith("PENDING"):
                existing_by_name = (
                    db.query(StudentRecord)
                    .filter(
                        StudentRecord.first_name == first_name,
                        StudentRecord.last_name == last_name,
                    )
                    .first()
                )
                if existing_by_name:
                    skipped += 1
                    continue

            record = StudentRecord(
                student_id=student_id,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                email=email,
                course=course,
                year_level=year_level,
                section=section,
                birthdate=birthdate,
                is_active=True,
            )
            db.add(record)
            added += 1

        # ---- Test student (CJ Jutba) ----
        ts = TEST_STUDENT
        if ts["student_id"] not in existing_ids:
            existing_by_name = (
                db.query(StudentRecord)
                .filter(
                    StudentRecord.first_name == ts["first_name"],
                    StudentRecord.last_name == ts["last_name"],
                )
                .first()
            )
            if not existing_by_name:
                record = StudentRecord(
                    student_id=ts["student_id"],
                    first_name=ts["first_name"],
                    last_name=ts["last_name"],
                    email=ts["email"],
                    course=ts["course"],
                    year_level=ts["year_level"],
                    section=ts["section"],
                    birthdate=ts["birthdate"],
                    contact_number=ts["contact_number"],
                    is_active=True,
                )
                db.add(record)
                added += 1
                print(f"  ADD   {ts['student_id']} — {ts['first_name']} {ts['last_name']} (test student)")
            else:
                skipped += 1
        else:
            print(f"  SKIP  {ts['student_id']} — already exists (test student)")
            skipped += 1

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
        print(f"\nTest student for registration:")
        print(f"  {ts['student_id']}  ({ts['first_name']} {ts['last_name']})  DOB: {ts['birthdate']}")

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
