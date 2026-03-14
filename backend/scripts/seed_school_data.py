"""
Seed School Data Script

Parses docs/data/ListofStudents_All-thesis-purposes.md and seeds the database
with real school data for the IAMS pilot deployment at JRMSU.

Creates:
- 3 Faculty user accounts (password: password123) in users table
- 3 Faculty records in faculty_records table
- 2 Rooms (EB226, EB227) in rooms table
- Schedules for all class sections in schedules table
- Deduplicated student records (~160) in student_records table

Run from backend directory:
    python -m scripts.seed_school_data

Idempotent — skips existing records on re-run.
"""

import re
import sys
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import logger, settings
from app.database import SessionLocal
from app.models.faculty_record import FacultyRecord
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.student_record import StudentRecord
from app.models.user import User, UserRole
from app.utils.security import hash_password

# ─── Constants ─────────────────────────────────────────────────────

MARKDOWN_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "data"
    / "ListofStudents_All-thesis-purposes.md"
)
DEFAULT_PASSWORD = "password123"
SEMESTER = "2nd"
ACADEMIC_YEAR = "2025-2026"

# ─── Faculty Definitions ───────────────────────────────────────────

FACULTY_DEFS = [
    {
        "faculty_id": "FAC-ELUMBA",
        "first_name": "Ryan",
        "last_name": "Elumba",
        "email": "ryan.elumba@jrmsu.edu.ph",
        "department": "Computer Engineering",
    },
    {
        "faculty_id": "FAC-GAHISAN",
        "first_name": "Maricon Denber",
        "last_name": "Gahisan",
        "email": "maricon.gahisan@jrmsu.edu.ph",
        "department": "Computer Engineering",
    },
    {
        "faculty_id": "FAC-LASCO",
        "first_name": "Troy",
        "last_name": "Lasco",
        "email": "troy.lasco@jrmsu.edu.ph",
        "department": "Computer Engineering",
    },
]

# ─── Room Definitions ──────────────────────────────────────────────

ROOM_DEFS = [
    {"name": "EB226", "building": "Engineering Building", "capacity": 50},
    {"name": "EB227", "building": "Engineering Building", "capacity": 50},
]

# ─── Schedule Definitions ──────────────────────────────────────────
# (subject_code, subject_name, faculty_email, room_name,
#  target_course, target_year_level, days[], start_time, end_time)
# day_of_week: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri

SCHEDULE_DEFS = [
    # ── Elumba ──
    ("CpE 121", "WEB Technologies (LEC)", "ryan.elumba@jrmsu.edu.ph",
     "EB227", "BSCPE", 2, [1, 3], time(7, 0), time(8, 30)),
    ("CpE 121L", "WEB Technologies (LAB)", "ryan.elumba@jrmsu.edu.ph",
     "EB227", "BSCPE", 2, [1, 3], time(14, 30), time(16, 0)),
    ("CpE 115", "Computer Hardware Fundamentals", "ryan.elumba@jrmsu.edu.ph",
     "EB226", "BSCPE", 1, [0, 2], time(13, 0), time(14, 30)),
    ("CpE 326", "CpE Laws & Professional Practice", "ryan.elumba@jrmsu.edu.ph",
     "EB227", "BSCPE", 3, [0, 2], time(17, 30), time(18, 30)),
    # ── Gahisan ──
    ("CpE 115", "Computer Hardware Fundamentals", "maricon.gahisan@jrmsu.edu.ph",
     "EB226", "BSCPE", 1, [0, 2], time(9, 0), time(10, 30)),
    ("CpE 120", "Fundamentals of Electronic Circuits", "maricon.gahisan@jrmsu.edu.ph",
     "EB226", "BSCPE", 2, [1, 3], time(10, 30), time(12, 0)),
    ("CpE 324", "Methods of Research & Writing", "maricon.gahisan@jrmsu.edu.ph",
     "EB226", "BSCPE", 3, [0, 2], time(10, 30), time(12, 0)),
    ("CpE 322", "Computer Networks & Security (LEC)", "maricon.gahisan@jrmsu.edu.ph",
     "EB226", "BSCPE", 3, [0, 2], time(14, 30), time(16, 0)),
    ("CpE 322L", "Computer Networks & Security (LAB)", "maricon.gahisan@jrmsu.edu.ph",
     "EB226", "BSCPE", 3, [0, 2], time(16, 0), time(17, 30)),
    ("CpE 421", "CpE Practice & Design 2", "maricon.gahisan@jrmsu.edu.ph",
     "EB226", "BSCPE", 4, [1, 3], time(14, 30), time(17, 30)),
    # ── Lasco ──
    ("ES 112", "Computer Programming", "troy.lasco@jrmsu.edu.ph",
     "EB227", "BSECE", 1, [0, 2], time(13, 0), time(14, 30)),
    ("ES 112", "Computer Programming", "troy.lasco@jrmsu.edu.ph",
     "EB227", "BSECE", 1, [1, 3], time(17, 30), time(19, 0)),
    ("CpE 113", "Object-Oriented Programming", "troy.lasco@jrmsu.edu.ph",
     "EB227", "BSCPE", 1, [1, 3], time(9, 0), time(12, 0)),
    ("CpE 113", "Object-Oriented Programming", "troy.lasco@jrmsu.edu.ph",
     "EB227", "BSCPE", 1, [0, 2], time(9, 0), time(12, 0)),
]


# ─── Helpers ───────────────────────────────────────────────────────


def parse_name(full_name: str) -> tuple[str, str | None, str]:
    """
    Parse 'LASTNAME, FIRSTNAME MIDDLENAME' → (first, middle, last).

    Filipino naming convention: the last word after the comma is typically
    the middle name (mother's maiden surname). Everything before is the
    first name (which may be compound, e.g., "MC LAURENCE").
    """
    full_name = full_name.strip()
    if not full_name:
        return ("", None, "")

    if "," not in full_name:
        return (full_name.title(), None, "")

    last_part, first_part = full_name.split(",", 1)
    last_name = last_part.strip().title()
    words = first_part.strip().split()

    if not words:
        return ("", None, last_name)
    if len(words) == 1:
        return (words[0].title(), None, last_name)

    # Last word = middle name (mother's maiden surname)
    first_name = " ".join(words[:-1]).title()
    middle_name = words[-1].title()
    return (first_name, middle_name, last_name)


def parse_date_str(date_str: str) -> date | None:
    """Parse flexible date formats: MM/DD/YYYY, MM/DD/YY, MMDD/YY."""
    date_str = date_str.strip()
    if not date_str:
        return None

    parts = date_str.split("/")

    if len(parts) == 3:
        try:
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y = 2000 + y if y <= 25 else 1900 + y
            return date(y, m, d)
        except (ValueError, TypeError):
            pass

    # Handle "0411/06" → month=04, day=11, year=06
    if len(parts) == 2:
        first, second = parts
        if len(first) == 4 and len(second) == 2:
            try:
                m, d = int(first[:2]), int(first[2:])
                y = int(second)
                y = 2000 + y if y <= 25 else 1900 + y
                return date(y, m, d)
            except (ValueError, TypeError):
                pass

    print(f"  WARNING: Could not parse date '{date_str}'")
    return None


def normalize_student_id(sid: str) -> str:
    """Normalize student ID format. Returns empty string if blank."""
    sid = sid.strip()
    if not sid:
        return ""

    # Fix missing dash: "24-A01549" → "24-A-01549"
    match = re.match(r"^(\d{2})-([A-Za-z])(\d+)$", sid)
    if match:
        return f"{match.group(1)}-{match.group(2).upper()}-{match.group(3)}"

    return sid.strip()


def infer_year_level(student_id: str) -> int | None:
    """Infer year level from student ID enrollment year prefix."""
    if not student_id or student_id.startswith("PENDING"):
        return None

    match = re.match(r"^(\d{2})-", student_id)
    if not match:
        return None

    enrollment_year = 2000 + int(match.group(1))
    # Current academic year 2025-2026
    years_since = 2025 - enrollment_year + 1
    return min(max(years_since, 1), 4)


def infer_section(student_id: str) -> str | None:
    """Extract section letter from student ID (e.g., 'A' from '24-A-00233')."""
    if not student_id or student_id.startswith("PENDING"):
        return None

    match = re.match(r"^\d{2}-([A-Za-z])-", student_id)
    return match.group(1).upper() if match else None


# ─── Markdown Parser ───────────────────────────────────────────────


def parse_students_from_md(filepath: Path) -> list[dict]:
    """
    Parse student data from the markdown file.

    Returns list of dicts with keys: name, email, birthdate, student_id, program.
    Students may appear multiple times (enrolled in multiple sections).
    """
    content = filepath.read_text(encoding="utf-8")
    entries = []
    current_program = "CpE"
    in_student_table = False

    for line in content.split("\n"):
        # Track program from metadata lines
        if "**Program:**" in line:
            prog = line.split("**Program:**")[1].strip()
            if prog:
                current_program = prog
        elif line.startswith("### ") and "Program:" in line:
            for part in line.split("|"):
                if "Program:" in part:
                    prog = part.split("Program:")[1].strip()
                    if prog:
                        current_program = prog

        # Student table header row
        if "| No. |" in line:
            in_student_table = True
            continue

        # Student data row
        if in_student_table and line.startswith("|"):
            # Skip table separator
            if "|---" in line:
                continue

            data_cells = [c.strip() for c in line.split("|")[1:-1]]

            if len(data_cells) >= 2 and data_cells[0].isdigit():
                entries.append({
                    "name": data_cells[1] if len(data_cells) > 1 else "",
                    "email": data_cells[2] if len(data_cells) > 2 else "",
                    "birthdate": data_cells[3] if len(data_cells) > 3 else "",
                    "student_id": data_cells[4] if len(data_cells) > 4 else "",
                    "program": current_program,
                })

        # End of student table (non-pipe line)
        elif in_student_table:
            in_student_table = False

    return entries


def deduplicate_students(entries: list[dict]) -> list[dict]:
    """
    Deduplicate students by normalized name.
    Merges data, preferring non-empty values from earlier appearances.
    """
    merged: dict[str, dict] = {}

    for entry in entries:
        name_key = entry["name"].strip().upper()
        if not name_key:
            continue

        if name_key in merged:
            existing = merged[name_key]
            # Merge: keep first non-empty value for each field
            for field in ("email", "birthdate", "student_id"):
                if not existing[field] and entry[field]:
                    existing[field] = entry[field]
            # Mark as ECE if student appears in any ECE section
            if entry["program"] == "ECE":
                existing["program"] = "ECE"
        else:
            merged[name_key] = {**entry}

    return list(merged.values())


# ─── Supabase Auth Sync ───────────────────────────────────────────


def _sync_supabase_auth_user(email: str, password: str, metadata: dict) -> str | None:
    """Create user in Supabase Auth if configured. Returns Supabase user ID or None."""
    if not settings.USE_SUPABASE_AUTH:
        return None
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return None

    import requests

    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        for u in resp.json().get("users", []):
            if u.get("email") == email:
                print(f"    [Supabase] {email} already exists")
                return u.get("id")

        resp = requests.post(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": metadata,
            },
            timeout=10,
        )
        resp.raise_for_status()
        sb_id = resp.json().get("id")
        print(f"    [Supabase] Created {email}")
        return sb_id
    except Exception as e:
        print(f"    [Supabase] Warning: {e}")
        return None


# ─── Main Seed Function ───────────────────────────────────────────


def seed():
    """Seed database with real school data from the markdown file."""
    if not MARKDOWN_PATH.exists():
        print(f"ERROR: Markdown file not found: {MARKDOWN_PATH}")
        return

    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Real School Data")
        print("=" * 60)

        # ── 1. Faculty ──────────────────────────────────────────────
        print("\n[1/4] Creating faculty accounts...")
        faculty_map: dict[str, User] = {}  # email → User

        for fdef in FACULTY_DEFS:
            existing = db.query(User).filter(User.email == fdef["email"]).first()
            if existing:
                print(f"  SKIP  {fdef['email']} (ID: {existing.id})")
                faculty_map[fdef["email"]] = existing
            else:
                user = User(
                    email=fdef["email"],
                    password_hash=hash_password(DEFAULT_PASSWORD),
                    role=UserRole.FACULTY,
                    first_name=fdef["first_name"],
                    last_name=fdef["last_name"],
                    is_active=True,
                    email_verified=True,
                )
                db.add(user)
                db.flush()
                faculty_map[fdef["email"]] = user
                print(f"  ADD   {fdef['first_name']} {fdef['last_name']} ({fdef['email']})")

                sb_id = _sync_supabase_auth_user(
                    fdef["email"],
                    DEFAULT_PASSWORD,
                    {
                        "first_name": fdef["first_name"],
                        "last_name": fdef["last_name"],
                        "role": "faculty",
                    },
                )
                if sb_id:
                    user.supabase_user_id = sb_id
                    db.flush()

            # Faculty record
            existing_fr = (
                db.query(FacultyRecord)
                .filter(FacultyRecord.faculty_id == fdef["faculty_id"])
                .first()
            )
            if not existing_fr:
                fr = FacultyRecord(
                    faculty_id=fdef["faculty_id"],
                    first_name=fdef["first_name"],
                    last_name=fdef["last_name"],
                    email=fdef["email"],
                    department=fdef["department"],
                    is_active=True,
                )
                db.add(fr)
                print(f"    + Faculty record: {fdef['faculty_id']}")

        # ── 2. Rooms ────────────────────────────────────────────────
        print("\n[2/4] Creating rooms...")
        room_map: dict[str, Room] = {}  # name → Room

        for rdef in ROOM_DEFS:
            existing = db.query(Room).filter(Room.name == rdef["name"]).first()
            if existing:
                print(f"  SKIP  {rdef['name']} (ID: {existing.id})")
                room_map[rdef["name"]] = existing
            else:
                room = Room(
                    name=rdef["name"],
                    building=rdef["building"],
                    capacity=rdef["capacity"],
                    is_active=True,
                )
                db.add(room)
                db.flush()
                room_map[rdef["name"]] = room
                print(f"  ADD   {rdef['name']} ({rdef['building']})")

        # ── 3. Schedules ────────────────────────────────────────────
        print("\n[3/4] Creating schedules...")
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        schedule_count = 0

        for sdef in SCHEDULE_DEFS:
            (
                subj_code, subj_name, fac_email, room_name,
                target_course, target_year, days, start, end,
            ) = sdef

            faculty = faculty_map[fac_email]
            room = room_map[room_name]

            for day_idx in days:
                existing = (
                    db.query(Schedule)
                    .filter(
                        Schedule.subject_code == subj_code,
                        Schedule.faculty_id == faculty.id,
                        Schedule.day_of_week == day_idx,
                        Schedule.start_time == start,
                    )
                    .first()
                )
                if existing:
                    print(
                        f"  SKIP  {subj_code} {day_names[day_idx]} "
                        f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
                    )
                else:
                    sched = Schedule(
                        subject_code=subj_code,
                        subject_name=subj_name,
                        faculty_id=faculty.id,
                        room_id=room.id,
                        day_of_week=day_idx,
                        start_time=start,
                        end_time=end,
                        semester=SEMESTER,
                        academic_year=ACADEMIC_YEAR,
                        target_course=target_course,
                        target_year_level=target_year,
                        is_active=True,
                    )
                    db.add(sched)
                    schedule_count += 1
                    fac_short = fac_email.split("@")[0]
                    print(
                        f"  ADD   {subj_code} {day_names[day_idx]} "
                        f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} "
                        f"({fac_short}, {room_name})"
                    )

        db.flush()

        # ── 4. Student Records ──────────────────────────────────────
        print("\n[4/4] Parsing and seeding student records...")

        raw_entries = parse_students_from_md(MARKDOWN_PATH)
        print(f"  Raw entries parsed: {len(raw_entries)}")

        students = deduplicate_students(raw_entries)
        print(f"  Unique students after dedup: {len(students)}")

        used_ids: set[str] = set()
        pending_counter = 1
        added = 0
        skipped = 0
        warnings: list[str] = []

        # Pre-load existing student IDs for idempotency
        existing_ids = {
            r.student_id for r in db.query(StudentRecord.student_id).all()
        }

        for student in students:
            first_name, middle_name, last_name = parse_name(student["name"])
            email = student["email"].lower().strip() if student["email"] else None
            birthdate = parse_date_str(student["birthdate"])
            raw_sid = normalize_student_id(student["student_id"])

            # Determine course
            course = "BSECE" if student["program"] == "ECE" else "BSCPE"

            # Assign student ID (generate PENDING if missing or duplicate)
            if raw_sid and raw_sid not in used_ids:
                student_id = raw_sid
            elif raw_sid and raw_sid in used_ids:
                warnings.append(
                    f"Duplicate ID {raw_sid} for {student['name']} -> assigned PENDING"
                )
                student_id = f"PENDING-{pending_counter:04d}"
                pending_counter += 1
            else:
                student_id = f"PENDING-{pending_counter:04d}"
                pending_counter += 1

            used_ids.add(student_id)

            # Infer year level and section from student ID
            year_level = infer_year_level(student_id)
            section = infer_section(student_id)

            # Idempotency check
            if student_id in existing_ids:
                skipped += 1
                continue

            # For PENDING IDs, also check by name to avoid duplicates on re-run
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
                email=email or None,
                course=course,
                year_level=year_level,
                section=section,
                birthdate=birthdate,
                contact_number=None,
                is_active=True,
            )
            db.add(record)
            added += 1

        # ── Commit ──────────────────────────────────────────────────
        db.commit()
        logger.info("School data seeded successfully")

        # ── Summary ─────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("SCHOOL DATA SEED COMPLETE")
        print("=" * 60)

        print(f"\nFaculty Accounts ({len(FACULTY_DEFS)}):")
        for fdef in FACULTY_DEFS:
            print(
                f"  {fdef['first_name']} {fdef['last_name']} "
                f"- {fdef['email']} (password: {DEFAULT_PASSWORD})"
            )

        print(f"\nRooms: {len(ROOM_DEFS)}")
        for rdef in ROOM_DEFS:
            print(f"  {rdef['name']} ({rdef['building']})")

        print(f"\nSchedules: {schedule_count} entries created")

        print(f"\nStudent Records: {added} added, {skipped} skipped")
        pending = sum(1 for s in used_ids if s.startswith("PENDING"))
        if pending:
            print(f"  ({pending} students assigned PENDING IDs — update later)")

        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for w in warnings:
                print(f"  ! {w}")

        print(
            f"\nNote: Enrollment records require user accounts (created during "
            f"mobile app registration). Auto-enrollment matches students to "
            f"schedules by course + year level. For precise section assignment, "
            f"use the manual enrollment UI."
        )

    except Exception as e:
        db.rollback()
        logger.error(f"School data seed failed: {e}")
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
