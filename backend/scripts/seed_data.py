"""
Seed Data Script for IAMS Backend

Creates operational data for development and thesis demonstration.
Populates the database with faculty users, 2 rooms (EB226, EB227),
and all class schedules from the JRMSU CpE department.

Data is based on: docs/data/ListofStudents_All-thesis-purposes.md

Faculty accounts (all use password123):
  - faculty@gmail.com          (default test account)
  - ryan.elumba@jrmsu.edu.ph   (Elumba, Ryan Z.)
  - maricon.gahisan@jrmsu.edu.ph (Gahisan, Maricon Denber)
  - troy.lasco@jrmsu.edu.ph    (Lasco, Troy C.)

NOTE: Student accounts are NOT pre-created. Students must self-register
through the mobile app using their Student ID from student_records table.

Run from backend directory:
    python -m scripts.seed_data

This script is idempotent -- it checks for existing seed data before inserting.
"""

import sys
from pathlib import Path

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import time
from app.database import SessionLocal, engine, Base
from app.models import User, UserRole, Room, Schedule
from app.utils.security import hash_password
from app.config import logger


# ---------------------------------------------------------------------------
# Faculty definitions: default test account + 3 real JRMSU instructors
# (email, first_name, last_name)
# ---------------------------------------------------------------------------
FACULTY_DEFS = [
    ("faculty@gmail.com",              "Faculty",        "User"),
    ("faculty.eb226@gmail.com",        "Faculty",        "EB226"),
    ("faculty.eb227@gmail.com",        "Faculty",        "EB227"),
    ("ryan.elumba@jrmsu.edu.ph",       "Ryan",           "Elumba"),
    ("maricon.gahisan@jrmsu.edu.ph",   "Maricon Denber", "Gahisan"),
    ("troy.lasco@jrmsu.edu.ph",        "Troy",           "Lasco"),
]

# ---------------------------------------------------------------------------
# Room definitions: 2 rooms from JRMSU Engineering Building
# (name, building, capacity, camera_endpoint, stream_key)
#   camera_endpoint = raw RTSP URL for backend face recognition
#   stream_key      = MediaMTX path name for mobile app streaming
# ---------------------------------------------------------------------------
ROOM_DEFS = [
    ("EB226", "Engineering Building", 50,
     "rtsp://host.docker.internal:8554/eb226-recognition",  # Sub stream for recognition
     "eb226"),  # HD stream key for app WebRTC
    ("EB227", "Engineering Building", 50,
     "rtsp://host.docker.internal:8554/eb227-recognition",  # Sub stream for recognition
     "eb227"),  # HD stream key for app WebRTC
]

# ---------------------------------------------------------------------------
# Schedule definitions from ListofStudents_All-thesis-purposes.md
# (subject_code, subject_name, year_level, target_course, days, start, end, room_name, faculty_email)
#
# day_of_week: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
# ---------------------------------------------------------------------------
SCHEDULE_DEFS = [
    # ── Test schedules (24/7 for testing) ────────────────────────────
    # Default faculty — test in EB226
    ("TEST 000", "IAMS Test Class (24/7)",             0, "BSCPE", [0, 1, 2, 3, 4, 5, 6], time(0, 0), time(23, 59), "EB226", "faculty@gmail.com"),
    # Faculty EB226 — dedicated 24/7 test in EB226
    ("TEST 226", "IAMS Test EB226 (24/7)",             0, "BSCPE", [0, 1, 2, 3, 4, 5, 6], time(0, 0), time(23, 59), "EB226", "faculty.eb226@gmail.com"),
    # Faculty EB227 — dedicated 24/7 test in EB227
    ("TEST 227", "IAMS Test EB227 (24/7)",             0, "BSCPE", [0, 1, 2, 3, 4, 5, 6], time(0, 0), time(23, 59), "EB227", "faculty.eb227@gmail.com"),

    # ── Elumba ─────────────────────────────────────────────────────────
    # CpE 121 / CpE 121L — WEB Technologies (EB227, TTH)
    ("CpE 121",  "WEB Technologies (LEC)",              2, "BSCPE", [1, 3], time(7, 0),   time(8, 30),  "EB227", "ryan.elumba@jrmsu.edu.ph"),
    ("CpE 121L", "WEB Technologies (LAB)",              2, "BSCPE", [1, 3], time(14, 30), time(16, 0),  "EB227", "ryan.elumba@jrmsu.edu.ph"),
    # CpE 115 — Computer Hardware Fundamentals (EB226, MW)
    ("CpE 115",  "Computer Hardware Fundamentals",      1, "BSCPE", [0, 2], time(13, 0),  time(14, 30), "EB226", "ryan.elumba@jrmsu.edu.ph"),
    # CpE 326 — CpE Laws & Professional Practice (EB227, MW)
    ("CpE 326",  "CpE Laws & Professional Practice",   3, "BSCPE", [0, 2], time(17, 30), time(18, 30), "EB227", "ryan.elumba@jrmsu.edu.ph"),

    # ── Gahisan ────────────────────────────────────────────────────────
    # CpE 115 — Computer Hardware Fundamentals (EB226, MW) — section 2
    ("CpE 115",  "Computer Hardware Fundamentals",      1, "BSCPE", [0, 2], time(9, 0),   time(10, 30), "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    # CpE 120 — Fundamentals of Electronic Circuits (EB226, TTH)
    ("CpE 120",  "Fundamentals of Electronic Circuits", 2, "BSCPE", [1, 3], time(10, 30), time(12, 0),  "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    # CpE 324 — Methods of Research & Writing (EB226, MW)
    ("CpE 324",  "Methods of Research & Writing",       3, "BSCPE", [0, 2], time(10, 30), time(12, 0),  "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    # CpE 322 / CpE 322L — Computer Networks & Security (EB226, MW)
    ("CpE 322",  "Computer Networks & Security (LEC)",  3, "BSCPE", [0, 2], time(14, 30), time(16, 0),  "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    ("CpE 322L", "Computer Networks & Security (LAB)",  3, "BSCPE", [0, 2], time(16, 0),  time(17, 30), "EB226", "maricon.gahisan@jrmsu.edu.ph"),
    # CpE 421 — CpE Practice & Design 2 (EB226, TTH)
    ("CpE 421",  "CpE Practice & Design 2",            4, "BSCPE", [1, 3], time(14, 30), time(17, 30), "EB226", "maricon.gahisan@jrmsu.edu.ph"),

    # ── Lasco ──────────────────────────────────────────────────────────
    # ES 112 — Computer Programming (EB227, MW + TTH sections)
    ("ES 112",   "Computer Programming",                1, "BSECE", [0, 2], time(13, 0),  time(14, 30), "EB227", "troy.lasco@jrmsu.edu.ph"),
    ("ES 112",   "Computer Programming",                1, "BSECE", [1, 3], time(17, 30), time(19, 0),  "EB227", "troy.lasco@jrmsu.edu.ph"),
    # CpE 113 — Object-Oriented Programming (EB227, TTH + MW sections)
    ("CpE 113",  "Object-Oriented Programming",         1, "BSCPE", [1, 3], time(9, 0),   time(12, 0),  "EB227", "troy.lasco@jrmsu.edu.ph"),
    ("CpE 113",  "Object-Oriented Programming",         1, "BSCPE", [0, 2], time(9, 0),   time(12, 0),  "EB227", "troy.lasco@jrmsu.edu.ph"),
]


def _create_faculty_user(db, email, first_name, last_name, common_hash):
    """Create a single faculty user."""
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
    print(f"  Created: {first_name} {last_name} ({email}, ID: {user.id})")
    return user


def seed():
    """
    Main seed function.

    Creates the following data in a single transaction:
      1. Faculty users (default + 3 real JRMSU instructors, all password123)
      2. Admin user (admin@admin.com / admin123)
      3. 2 Rooms (EB226, EB227)
      4. All schedules assigned to the correct instructor

    Students must self-register via mobile app (no pre-created student users).
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Database")
        print("=" * 60)

        # ------------------------------------------------------------------
        # Idempotency check: skip if seed data already exists
        # ------------------------------------------------------------------
        existing_faculty = db.query(User).filter(
            User.email == "faculty@gmail.com"
        ).first()

        # Check what already exists — only create what's missing
        has_rooms = db.query(Room).count() > 0
        has_schedules = db.query(Schedule).count() > 0

        if existing_faculty and has_rooms and has_schedules:
            print("\nSeed data already exists. Skipping...")
            print(f"  Faculty: {existing_faculty.email} (ID: {existing_faculty.id})")
            room_count = db.query(Room).count()
            schedule_count = db.query(Schedule).count()
            faculty_count = db.query(User).filter(User.role == UserRole.FACULTY).count()
            print(f"  Faculty: {faculty_count}")
            print(f"  Rooms: {room_count}")
            print(f"  Schedules: {schedule_count}")
            print("\nNo changes made.")
            return

        # ------------------------------------------------------------------
        # 1. Create Faculty Users + Admin User
        # ------------------------------------------------------------------
        print("\n[1/3] Creating faculty and admin users...")
        common_hash = hash_password("password123")  # Compute once (bcrypt is slow)

        faculty_map: dict[str, User] = {}  # email → User
        for email, first_name, last_name in FACULTY_DEFS:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                faculty_map[email] = existing
                print(f"  Exists: {first_name} {last_name} ({email}, ID: {existing.id})")
            else:
                user = _create_faculty_user(db, email, first_name, last_name, common_hash)
                faculty_map[email] = user

        # Create Admin User (if not exists)
        admin = db.query(User).filter(User.email == "admin@admin.com").first()
        if not admin:
            admin = User(
                email="admin@admin.com",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                first_name="System",
                last_name="Admin",
                is_active=True,
                email_verified=True,
            )
            db.add(admin)
            db.flush()
            print(f"  Created: {admin.first_name} {admin.last_name} ({admin.email}, ID: {admin.id})")
        else:
            print(f"  Exists: {admin.first_name} {admin.last_name} ({admin.email}, ID: {admin.id})")

        # ------------------------------------------------------------------
        # 2. Create Rooms
        # ------------------------------------------------------------------
        print("\n[2/3] Creating rooms...")
        room_map: dict[str, Room] = {}
        for name, building, capacity, camera_endpoint, stream_key in ROOM_DEFS:
            existing = db.query(Room).filter(Room.name == name).first()
            if existing:
                room_map[name] = existing
                print(f"  Exists: {name} (ID: {existing.id})")
            else:
                room = Room(
                    name=name,
                    building=building,
                    capacity=capacity,
                    camera_endpoint=camera_endpoint or None,
                    stream_key=stream_key or None,
                    is_active=True,
                )
                db.add(room)
                db.flush()
                room_map[name] = room
                print(f"  Created: {name} in {building} (capacity: {capacity}, ID: {room.id})")

        # ------------------------------------------------------------------
        # 3. Create Schedules (assigned to correct instructor)
        # ------------------------------------------------------------------
        print("\n[3/3] Creating schedules...")
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        total_schedules = 0

        for (subject_code, subject_name, year_level, target_course,
             days, start, end, room_name, faculty_email) in SCHEDULE_DEFS:
            room = room_map[room_name]
            faculty = faculty_map[faculty_email]

            for day_idx in days:
                schedule = Schedule(
                    subject_code=subject_code,
                    subject_name=subject_name,
                    faculty_id=faculty.id,
                    room_id=room.id,
                    day_of_week=day_idx,
                    start_time=start,
                    end_time=end,
                    semester="2nd",
                    academic_year="2025-2026",
                    target_course=target_course,
                    target_year_level=year_level,
                    is_active=True,
                )
                db.add(schedule)
                db.flush()
                total_schedules += 1
                fac_short = faculty_email.split("@")[0]
                print(f"  {subject_code} (Year {year_level}) — {day_names[day_idx]} "
                      f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} in {room_name} [{fac_short}]")

        # ------------------------------------------------------------------
        # Commit the entire transaction
        # ------------------------------------------------------------------
        db.commit()
        logger.info("Seed data committed successfully")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("SEED DATA COMPLETE")
        print("=" * 60)
        print(f"\nAdmin Login (web dashboard):")
        print(f"  Email:      admin@admin.com")
        print(f"  Password:   admin123")
        print(f"\nFaculty Logins (all use password123):")
        for email, first_name, last_name in FACULTY_DEFS:
            print(f"  {email:<35} ({first_name} {last_name})")
        print(f"\nRooms: {len(ROOM_DEFS)}")
        for name, building, *_ in ROOM_DEFS:
            print(f"  {name} ({building})")
        print(f"\nSchedules: {total_schedules} total")
        for entry in SCHEDULE_DEFS:
            subj_code, subj_name, year, course, days, start, end, room, fac_email = entry
            day_str = "/".join(day_names[d][:3] for d in days)
            fac_short = fac_email.split("@")[0]
            print(f"  {subj_code:<10} (Year {year}) {day_str} "
                  f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} in {room} [{fac_short}]")
        print(f"\nStudents: Use mobile app to self-register with Student ID from student_records")
        print(f"  Upon registration, students are auto-enrolled in matching schedules")

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
