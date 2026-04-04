"""
IAMS Database Seed Script (Unified)

Wipes ALL data and reseeds the database from scratch with:
  - ~160 student records (parsed from docs/data/ListofStudents_All-thesis-purposes.md)
  - 5 faculty records (2 test + 3 real JRMSU instructors)
  - 2 faculty user accounts (faculty.eb226@gmail.com, faculty.eb227@gmail.com)
  - 1 admin account (admin@admin.com / 123)
  - 2 rooms (EB226, EB227)
  - All class schedules (2 test 24/7 + 15 real courses)
  - System settings
  - Faculty notifications

NO simulation data. NO pre-created student users.
Students self-register via the mobile app using their Student ID.

Usage:
    docker compose exec -T api-gateway python -m scripts.seed_data
"""

import re
import shutil
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.config import logger, settings
from app.database import SessionLocal
from app.models import (
    FacultyRecord,
    Notification,
    Room,
    Schedule,
    StudentRecord,
    SystemSetting,
    User,
    UserRole,
)
from app.utils.security import hash_password

# ─── Constants ────────────────────────────────────────────────────────────────

MARKDOWN_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "data"
    / "ListofStudents_All-thesis-purposes.md"
)

SEMESTER = "2nd"
ACADEMIC_YEAR = "2025-2026"

# ─── Test Student ─────────────────────────────────────────────────────────────

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

# ─── Faculty Records (faculty_records table) ─────────────────────────────────

FACULTY_RECORDS = [
    ("FAC-001", "Faculty", "EB226", "faculty.eb226@gmail.com", "Computer Engineering"),
    ("FAC-002", "Faculty", "EB227", "faculty.eb227@gmail.com", "Computer Engineering"),
    ("FAC-003", "Ryan", "Elumba", "ryan.elumba@jrmsu.edu.ph", "Computer Engineering"),
    ("FAC-004", "Maricon Denber", "Gahisan", "maricon.gahisan@jrmsu.edu.ph", "Computer Engineering"),
    ("FAC-005", "Troy", "Lasco", "troy.lasco@jrmsu.edu.ph", "Computer Engineering"),
]

# ─── Faculty User Accounts (users table) ─────────────────────────────────────
# All faculty get login accounts (password123).
# (email, first_name, last_name)

FACULTY_USERS = [
    ("faculty.eb226@gmail.com", "Faculty", "EB226"),
    ("faculty.eb227@gmail.com", "Faculty", "EB227"),
    ("ryan.elumba@jrmsu.edu.ph", "Ryan", "Elumba"),
    ("maricon.gahisan@jrmsu.edu.ph", "Maricon Denber", "Gahisan"),
    ("troy.lasco@jrmsu.edu.ph", "Troy", "Lasco"),
]

# ─── Room Definitions ────────────────────────────────────────────────────────

ROOM_DEFS = [
    ("EB226", "Engineering Building", 50,
     "rtsp://mediamtx:8554/eb226", "eb226"),
    ("EB227", "Engineering Building", 50,
     "rtsp://mediamtx:8554/eb227", "eb227"),
]

# ─── Schedule Definitions ────────────────────────────────────────────────────
# (subject_code, subject_name, year_level, target_course, days, start, end, room_name, faculty_email)
# day_of_week: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

SCHEDULE_DEFS = [
    # ── Test schedules (24/7 for testing) ────────────────────────────
    ("TEST 226", "IAMS Test EB226 (24/7)", 4, "BSCPE", [0, 1, 2, 3, 4, 5, 6], time(0, 0), time(23, 59), "EB226", "faculty.eb226@gmail.com"),
    ("TEST 227", "IAMS Test EB227 (24/7)", 4, "BSCPE", [0, 1, 2, 3, 4, 5, 6], time(0, 0), time(23, 59), "EB227", "faculty.eb227@gmail.com"),

    # ── Elumba ────────────────────────────────────────────────────────
    ("CpE 121",  "WEB Technologies (LEC)",              2, "BSCPE", [1, 3], time(7, 0),   time(8, 30),  "EB227", "ryan.elumba@jrmsu.edu.ph"),
    ("CpE 121L", "WEB Technologies (LAB)",              2, "BSCPE", [1, 3], time(14, 30), time(16, 0),  "EB227", "ryan.elumba@jrmsu.edu.ph"),
    ("CpE 115",  "Computer Hardware Fundamentals",      1, "BSCPE", [0, 2], time(13, 0),  time(14, 30), "EB226", "ryan.elumba@jrmsu.edu.ph"),
    ("CpE 326",  "CpE Laws & Professional Practice",   3, "BSCPE", [0, 2], time(17, 30), time(18, 30), "EB227", "ryan.elumba@jrmsu.edu.ph"),

    # ── Gahisan ───────────────────────────────────────────────────────
    ("CpE 115",  "Computer Hardware Fundamentals",      1, "BSCPE", [0, 2], time(9, 0),   time(10, 30), "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    ("CpE 120",  "Fundamentals of Electronic Circuits", 2, "BSCPE", [1, 3], time(10, 30), time(12, 0),  "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    ("CpE 324",  "Methods of Research & Writing",       3, "BSCPE", [0, 2], time(10, 30), time(12, 0),  "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    ("CpE 322",  "Computer Networks & Security (LEC)",  3, "BSCPE", [0, 2], time(14, 30), time(16, 0),  "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    ("CpE 322L", "Computer Networks & Security (LAB)",  3, "BSCPE", [0, 2], time(16, 0),  time(17, 30), "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    ("CpE 421",  "CpE Practice & Design 2",            4, "BSCPE", [1, 3], time(14, 30), time(17, 30), "EB226", "maricon.gahisan@jrmsu.edu.ph"),

    # ── Lasco ─────────────────────────────────────────────────────────
    ("ES 112",   "Computer Programming",                1, "BSECE", [0, 2], time(13, 0),  time(14, 30), "EB227", "troy.lasco@jrmsu.edu.ph"),
    ("ES 112",   "Computer Programming",                1, "BSECE", [1, 3], time(17, 30), time(19, 0),  "EB227", "troy.lasco@jrmsu.edu.ph"),
    ("CpE 113",  "Object-Oriented Programming",         1, "BSCPE", [1, 3], time(9, 0),   time(12, 0),  "EB227", "troy.lasco@jrmsu.edu.ph"),
    ("CpE 113",  "Object-Oriented Programming",         1, "BSCPE", [0, 2], time(9, 0),   time(12, 0),  "EB227", "troy.lasco@jrmsu.edu.ph"),
]

# ─── System Settings ─────────────────────────────────────────────────────────

SYSTEM_SETTINGS = [
    ("scan_interval_seconds", "15"),
    ("early_leave_threshold", "3"),
    ("grace_period_minutes", "15"),
    ("recognition_threshold", "0.30"),
    ("session_buffer_minutes", "5"),
    ("academic_year", ACADEMIC_YEAR),
    ("semester", SEMESTER),
]

# ─── Notification Templates ──────────────────────────────────────────────────

NOTIFICATION_DEFS = [
    {
        "title": "Welcome to IAMS",
        "message": "Your faculty account has been set up. Students will appear in your class roster as they register through the mobile app.",
        "type": "system",
        "read": False,
        "created_at": datetime(2026, 2, 10, 8, 0),
    },
    {
        "title": "Classes Configured",
        "message": "Your class schedules have been configured for rooms EB226 and EB227 in the Engineering Building.",
        "type": "system",
        "read": True,
        "read_at": datetime(2026, 2, 10, 9, 0),
        "created_at": datetime(2026, 2, 10, 8, 30),
    },
    {
        "title": "System Ready",
        "message": "The IAMS attendance monitoring system is ready. The camera will automatically detect and track student attendance during class hours.",
        "type": "system",
        "read": False,
        "created_at": datetime(2026, 2, 11, 7, 0),
    },
    {
        "title": "Student Registration Open",
        "message": "Students can now register via the IAMS mobile app using their university Student ID. Registered students will be auto-enrolled in your classes based on their course and year level.",
        "type": "system",
        "read": False,
        "created_at": datetime(2026, 2, 11, 8, 0),
    },
    {
        "title": "Camera Setup Reminder",
        "message": "Please ensure the camera is positioned correctly and connected to the local network. Contact the admin if you need assistance.",
        "type": "alert",
        "read": False,
        "created_at": datetime(2026, 2, 12, 7, 0),
    },
]

ADMIN_NOTIFICATION_DEFS = [
    {
        "title": "Welcome to IAMS Admin",
        "message": "Your admin account is set up. Manage users, rooms, schedules, and monitor system status from this dashboard.",
        "type": "system",
        "read": False,
        "created_at": datetime(2026, 2, 10, 8, 0),
    },
    {
        "title": "System Configuration Complete",
        "message": "IAMS has been configured with 2 rooms (EB226, EB227), faculty accounts, and class schedules for the current semester.",
        "type": "system",
        "read": True,
        "read_at": datetime(2026, 2, 10, 9, 0),
        "created_at": datetime(2026, 2, 10, 8, 30),
    },
    {
        "title": "Attendance System Active",
        "message": "The facial recognition attendance system is online. Cameras in EB226 and EB227 are connected and scanning.",
        "type": "system",
        "read": False,
        "created_at": datetime(2026, 2, 11, 7, 0),
    },
    {
        "title": "Student Registration Open",
        "message": "Students can now self-register via the IAMS mobile app. Monitor registration progress from the Users page.",
        "type": "system",
        "read": False,
        "created_at": datetime(2026, 2, 11, 8, 0),
    },
    {
        "title": "Weekly Digest Available",
        "message": "Your first weekly attendance summary is ready. Review overall attendance rates and flagged students from the Analytics page.",
        "type": "alert",
        "read": False,
        "created_at": datetime(2026, 2, 17, 7, 0),
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Markdown Parser (absorbed from seed_school_data.py)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_name(full_name: str) -> tuple[str, str | None, str]:
    """Parse 'LASTNAME, FIRSTNAME MIDDLENAME' -> (first, middle, last)."""
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

    return None


def normalize_student_id(sid: str) -> str:
    """Normalize student ID format. Returns empty string if blank."""
    sid = sid.strip()
    if not sid:
        return ""
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
    years_since = 2025 - enrollment_year + 1
    return min(max(years_since, 1), 4)


def infer_section(student_id: str) -> str | None:
    """Extract section letter from student ID (e.g., 'A' from '24-A-00233')."""
    if not student_id or student_id.startswith("PENDING"):
        return None
    match = re.match(r"^\d{2}-([A-Za-z])-", student_id)
    return match.group(1).upper() if match else None


def parse_students_from_md(filepath: Path) -> list[dict]:
    """Parse student data from the markdown file."""
    content = filepath.read_text(encoding="utf-8")
    entries = []
    current_program = "CpE"
    in_student_table = False

    for line in content.split("\n"):
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

        if "| No. |" in line:
            in_student_table = True
            continue

        if in_student_table and line.startswith("|"):
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
        elif in_student_table:
            in_student_table = False

    return entries


def deduplicate_students(entries: list[dict]) -> list[dict]:
    """Deduplicate students by normalized name, merging non-empty values."""
    merged: dict[str, dict] = {}
    for entry in entries:
        name_key = entry["name"].strip().upper()
        if not name_key:
            continue
        if name_key in merged:
            existing = merged[name_key]
            for field in ("email", "birthdate", "student_id"):
                if not existing[field] and entry[field]:
                    existing[field] = entry[field]
            if entry["program"] == "ECE":
                existing["program"] = "ECE"
        else:
            merged[name_key] = {**entry}
    return list(merged.values())


# ═══════════════════════════════════════════════════════════════════════════════
# Seed Steps
# ═══════════════════════════════════════════════════════════════════════════════


def _wipe_all(db) -> None:
    """Truncate all tables (bypasses FK constraints)."""
    print("\n[1/8] Wiping all data...")
    db.execute(text("SET session_replication_role = 'replica'"))
    db.execute(text("""
        TRUNCATE TABLE
            refresh_tokens, presence_logs, early_leave_events,
            attendance_records, enrollments, schedules,
            face_embeddings, face_registrations, notifications,
            notification_preferences, rooms, users,
            student_records, faculty_records, system_settings
        CASCADE
    """))
    db.execute(text("SET session_replication_role = 'origin'"))
    db.flush()
    print("  All tables truncated.")


def _clear_faiss_and_faces() -> None:
    """Delete FAISS index and face upload files."""
    backend_dir = Path(__file__).resolve().parents[1]

    faiss_path = backend_dir / settings.FAISS_INDEX_PATH
    if faiss_path.exists():
        faiss_path.unlink()
        print(f"  Deleted FAISS index: {faiss_path}")
    else:
        print(f"  FAISS index already clean: {faiss_path}")

    faces_dir = backend_dir / "data" / "uploads" / "faces"
    if faces_dir.exists():
        count = 0
        for f in faces_dir.iterdir():
            if f.name != ".gitkeep":
                if f.is_dir():
                    shutil.rmtree(f)
                else:
                    f.unlink()
                count += 1
        print(f"  Cleared {count} face upload entries.")


def _seed_faculty_records(db) -> None:
    """Seed faculty_records table."""
    print("\n[2/8] Seeding faculty records...")
    for fac_id, first, last, email, dept in FACULTY_RECORDS:
        db.add(FacultyRecord(
            faculty_id=fac_id,
            first_name=first,
            last_name=last,
            email=email,
            department=dept,
            is_active=True,
        ))
        print(f"  {fac_id} — {first} {last} ({email})")
    db.flush()


def _seed_users(db) -> tuple[dict[str, User], User]:
    """Seed faculty user accounts + admin. Returns (email->User map, admin)."""
    print("\n[3/8] Creating user accounts...")
    common_hash = hash_password("password123")

    faculty_map: dict[str, User] = {}
    for email, first_name, last_name in FACULTY_USERS:
        user = User(
            email=email,
            password_hash=common_hash,
            role=UserRole.FACULTY,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.flush()
        faculty_map[email] = user
        print(f"  Faculty: {email} (ID: {user.id})")

    admin = User(
        email="admin@admin.com",
        password_hash=hash_password("123"),
        role=UserRole.ADMIN,
        first_name="System",
        last_name="Admin",
        is_active=True,
        email_verified=True,
    )
    db.add(admin)
    db.flush()
    print(f"  Admin:   admin@admin.com (ID: {admin.id})")

    return faculty_map, admin


def _seed_rooms(db) -> dict[str, Room]:
    """Seed rooms. Returns name->Room map."""
    print("\n[4/8] Creating rooms...")
    room_map: dict[str, Room] = {}
    for name, building, capacity, camera_endpoint, stream_key in ROOM_DEFS:
        room = Room(
            name=name,
            building=building,
            capacity=capacity,
            camera_endpoint=camera_endpoint,
            stream_key=stream_key,
            is_active=True,
        )
        db.add(room)
        db.flush()
        room_map[name] = room
        print(f"  {name} in {building} (capacity: {capacity}, ID: {room.id})")
    return room_map


def _seed_student_records(db) -> int:
    """Parse markdown and seed student_records. Returns count added."""
    print("\n[5/8] Seeding student records from school data...")

    if not MARKDOWN_PATH.exists():
        print(f"  WARNING: Markdown file not found: {MARKDOWN_PATH}")
        print("  Only seeding test student.")
        ts = TEST_STUDENT
        db.add(StudentRecord(**ts, is_active=True))
        db.flush()
        return 1

    raw = parse_students_from_md(MARKDOWN_PATH)
    students = deduplicate_students(raw)
    print(f"  Parsed {len(students)} unique students from markdown")

    used_ids: set[str] = set()
    pending_counter = 1
    added = 0

    for entry in students:
        first_name, middle_name, last_name = parse_name(entry["name"])
        email = entry["email"].lower().strip() if entry["email"] else None
        birthdate = parse_date_str(entry["birthdate"])
        raw_sid = normalize_student_id(entry["student_id"])
        course = "BSECE" if entry["program"] == "ECE" else "BSCPE"

        if raw_sid and raw_sid not in used_ids:
            student_id = raw_sid
        else:
            student_id = f"PENDING-{pending_counter:04d}"
            pending_counter += 1

        used_ids.add(student_id)

        db.add(StudentRecord(
            student_id=student_id,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            email=email or None,
            course=course,
            year_level=infer_year_level(student_id),
            section=infer_section(student_id),
            birthdate=birthdate,
            is_active=True,
        ))
        added += 1

    # Test student (CJ Jutba)
    ts = TEST_STUDENT
    if ts["student_id"] not in used_ids:
        db.add(StudentRecord(
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
        ))
        added += 1
        print(f"  Added test student: {ts['student_id']} — {ts['first_name']} {ts['last_name']}")

    db.flush()
    pending = sum(1 for s in used_ids if s.startswith("PENDING"))
    print(f"  Total: {added} student records ({pending} with PENDING IDs)")
    return added


def _seed_schedules(db, faculty_map: dict[str, User], room_map: dict[str, Room]) -> int:
    """Seed schedules. Returns total count. Uses faculty_map for FK lookup."""
    print("\n[6/8] Creating schedules...")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    fac_lookup = dict(faculty_map)

    total = 0
    for (subj_code, subj_name, year_level, target_course,
         days, start, end, room_name, faculty_email) in SCHEDULE_DEFS:
        faculty = fac_lookup[faculty_email]
        room = room_map[room_name]

        for day_idx in days:
            db.add(Schedule(
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
                target_year_level=year_level,
                is_active=True,
            ))
            total += 1
            fac_short = faculty_email.split("@")[0]
            print(f"  {subj_code:<10} Year {year_level} {day_names[day_idx]} "
                  f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} "
                  f"in {room_name} [{fac_short}]")

    db.flush()
    return total


def _seed_system_settings(db) -> None:
    """Seed system_settings table."""
    print("\n[7/8] Seeding system settings...")
    for key, value in SYSTEM_SETTINGS:
        db.add(SystemSetting(key=key, value=value))
        print(f"  {key} = {value}")
    db.flush()


def _seed_notifications(db, faculty_map: dict[str, User], admin: User) -> None:
    """Seed faculty + admin notifications."""
    print("\n[8/8] Creating notifications...")
    faculty = faculty_map["faculty.eb226@gmail.com"]
    for notif in NOTIFICATION_DEFS:
        db.add(Notification(user_id=faculty.id, **notif))
    for notif in ADMIN_NOTIFICATION_DEFS:
        db.add(Notification(user_id=admin.id, **notif))
    db.flush()
    total = len(NOTIFICATION_DEFS) + len(ADMIN_NOTIFICATION_DEFS)
    print(f"  Created {len(NOTIFICATION_DEFS)} notifications for {faculty.email}")
    print(f"  Created {len(ADMIN_NOTIFICATION_DEFS)} notifications for admin@admin.com")
    print(f"  Total: {total}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════


def seed():
    """Wipe everything and reseed the database from scratch."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Full Database Reset & Seed")
        print("=" * 60)

        _wipe_all(db)
        _clear_faiss_and_faces()

        _seed_faculty_records(db)
        faculty_map, admin_user = _seed_users(db)
        room_map = _seed_rooms(db)
        student_count = _seed_student_records(db)
        schedule_count = _seed_schedules(db, faculty_map, room_map)
        _seed_system_settings(db)
        _seed_notifications(db, faculty_map, admin_user)

        db.commit()
        logger.info("Database seeded successfully")

        # ── Summary ───────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"\n  Student records:  {student_count}")
        print(f"  Faculty records:  {len(FACULTY_RECORDS)}")
        print(f"  Rooms:            {len(ROOM_DEFS)}")
        print(f"  Schedules:        {schedule_count}")
        print(f"  System settings:  {len(SYSTEM_SETTINGS)}")
        print(f"  Notifications:    {len(NOTIFICATION_DEFS) + len(ADMIN_NOTIFICATION_DEFS)}")
        print(f"\nFaculty Logins (password123):")
        for email, first, last in FACULTY_USERS:
            print(f"  {email}")
        print(f"\nAdmin Login:")
        print(f"  admin@admin.com / 123")
        ts = TEST_STUDENT
        print(f"\nTest Student (for mobile app registration):")
        print(f"  {ts['student_id']} — {ts['first_name']} {ts['last_name']} (DOB: {ts['birthdate']})")

    except Exception as e:
        db.rollback()
        logger.error(f"Seed failed: {e}")
        print(f"\nERROR: Seed failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
