"""
Seed Data Script for IAMS Backend

Creates test data for development and thesis demonstration.
Populates the database with ONLY faculty user, rooms, and schedules.

NOTE: Student accounts are NOT pre-created. Students must self-register
through the mobile app using their Student ID from student_records table.
When they register, auto-enrollment matches them to schedules based on
their course and year level.

Run from backend directory:
    python -m scripts.seed_data

This script is idempotent -- it checks for existing seed data before inserting
and will skip gracefully if the data already exists.
"""

import sys
from pathlib import Path

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import time
from app.database import SessionLocal, engine, Base
from app.models import User, UserRole, Room, Schedule
from app.utils.security import hash_password
from app.config import settings, logger


def _sync_supabase_auth_user(email: str, password: str, metadata: dict) -> str | None:
    """
    Create (or skip if exists) a user in Supabase Auth so the mobile app
    can authenticate via supabase.auth.signInWithPassword().

    Uses the Supabase Admin REST API directly (no SDK needed).
    Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in backend .env.
    Silently skips if Supabase is not configured.

    Returns the Supabase Auth user ID (UUID string) or None.
    """
    if not settings.USE_SUPABASE_AUTH:
        print("  [Supabase Auth] Skipped — USE_SUPABASE_AUTH is disabled")
        return None

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        print("  [Supabase Auth] Skipped — SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return None

    import requests

    base_url = settings.SUPABASE_URL
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        # Check if user already exists
        resp = requests.get(f"{base_url}/auth/v1/admin/users", headers=headers, timeout=10)
        resp.raise_for_status()
        users = resp.json().get("users", [])
        for u in users:
            if u.get("email") == email:
                print(f"  [Supabase Auth] User {email} already exists — skipped")
                return u.get("id")

        # Create user with email_confirm=True so they can login immediately
        resp = requests.post(
            f"{base_url}/auth/v1/admin/users",
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
        print(f"  [Supabase Auth] Created user {email}")
        return sb_id
    except Exception as e:
        print(f"  [Supabase Auth] Warning: {e}")
        print("  (Continuing with local DB seed — Supabase Auth user can be created later)")
        return None


# ---------------------------------------------------------------------------
# Schedule definitions: (subject_code, subject_name, year_level, days, start, end)
# ---------------------------------------------------------------------------
SCHEDULE_DEFS = [
    # Year 4: CPE 401 — 24/7 lab for testing (always an active class)
    ("CPE 401", "Capstone Project Laboratory", 4, [0, 1, 2, 3, 4, 5, 6], time(0, 0), time(23, 59)),
    # Year 4: CPE 301 — every day 07:00-22:00 (main demo subject)
    ("CPE 301", "Microprocessors and Microcontrollers", 4, [0, 1, 2, 3, 4, 5, 6], time(7, 0), time(22, 0)),
    # Year 3: CPE 201 Mon-Fri + Sat
    ("CPE 201", "Digital Logic Design", 3, [0, 1, 2, 3, 4, 5], time(8, 0), time(10, 0)),
    # Year 2: CPE 101 Mon-Fri + Sat
    ("CPE 101", "Introduction to Computing", 2, [0, 1, 2, 3, 4, 5], time(9, 0), time(11, 0)),
    # Year 1: GE 101 Mon-Fri + Sat
    ("GE 101", "Mathematics in the Modern World", 1, [0, 1, 2, 3, 4, 5], time(13, 0), time(15, 0)),
]

# Room definitions: (name, building, capacity, camera_endpoint)
# camera_endpoint must be an RTSP URL for live streaming to work
ROOM_DEFS = [
    ("Room 301", "Engineering Building", 40, "rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_main"),
    ("Room 202", "Engineering Building", 35, ""),
    ("Room 103", "Engineering Building", 45, ""),
]

# Map subject to room by index: CPE 301 → Room 301, CPE 201 → Room 202, CPE 101 → Room 103, GE 101 → Room 103
SUBJECT_ROOM_MAP = {
    "CPE 401": 0,  # Room 301
    "CPE 301": 0,  # Room 301
    "CPE 201": 1,  # Room 202
    "CPE 101": 2,  # Room 103
    "GE 101": 2,   # Room 103
}


def seed():
    """
    Main seed function.

    Creates the following test data in a single transaction:
      1. Faculty user (faculty@gmail.com / password123)
      2. Rooms (Room 301, Room 202, Room 103)
      3. Schedules (5 subjects across all year levels, including weekends)

    All schedules are tagged with target_course="BSCPE" and appropriate
    target_year_level for auto-enrollment.

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

        if existing_faculty:
            print("\nSeed data already exists. Skipping...")
            print(f"  Faculty: {existing_faculty.email} (ID: {existing_faculty.id})")

            # Ensure admin account exists even if seed was run before admin was added
            existing_admin = db.query(User).filter(User.email == "admin@jrmsu.edu.ph").first()
            if not existing_admin:
                print("\n  Admin account missing — creating now...")
                admin = User(
                    email="admin@jrmsu.edu.ph",
                    password_hash=hash_password("admin123"),
                    role=UserRole.ADMIN,
                    first_name="System",
                    last_name="Admin",
                    is_active=True,
                    email_verified=True,
                )
                db.add(admin)
                db.commit()
                print(f"  Created: admin@jrmsu.edu.ph (ID: {admin.id})")
            else:
                print(f"  Admin: {existing_admin.email} (ID: {existing_admin.id})")

            room_count = db.query(Room).count()
            schedule_count = db.query(Schedule).count()
            print(f"  Rooms: {room_count}")
            print(f"  Schedules: {schedule_count}")
            print("\nNo changes made.")
            return

        # ------------------------------------------------------------------
        # 1. Create Faculty User + Admin User
        # ------------------------------------------------------------------
        print("\n[1/3] Creating faculty and admin users...")
        faculty = User(
            email="faculty@gmail.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY,
            first_name="Faculty",
            last_name="User",
            phone="09000000000",
            is_active=True,
            email_verified=True,
        )
        db.add(faculty)
        db.flush()
        print(f"  Created: {faculty.first_name} {faculty.last_name}")
        print(f"  Email:   {faculty.email}")
        print(f"  DB ID:   {faculty.id}")

        # Also create in Supabase Auth for mobile app login and link IDs
        sb_user_id = _sync_supabase_auth_user(
            email="faculty@gmail.com",
            password="password123",
            metadata={"first_name": "Faculty", "last_name": "User", "role": "faculty"},
        )
        if sb_user_id:
            faculty.supabase_user_id = sb_user_id
            db.flush()
            print(f"  Linked supabase_user_id: {sb_user_id}")

        # Create Admin User
        admin = User(
            email="admin@jrmsu.edu.ph",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            first_name="System",
            last_name="Admin",
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.flush()
        print(f"  Created: {admin.first_name} {admin.last_name}")
        print(f"  Email:   {admin.email}")
        print(f"  DB ID:   {admin.id}")

        # ------------------------------------------------------------------
        # 2. Create Rooms
        # ------------------------------------------------------------------
        print("\n[2/3] Creating rooms...")
        rooms = []
        for name, building, capacity, camera_endpoint in ROOM_DEFS:
            room = Room(
                name=name,
                building=building,
                capacity=capacity,
                camera_endpoint=camera_endpoint,
                is_active=True,
            )
            db.add(room)
            db.flush()
            rooms.append(room)
            print(f"  Created: {name} in {building} (capacity: {capacity}, ID: {room.id})")

        # ------------------------------------------------------------------
        # 3. Create Schedules (all year levels)
        # ------------------------------------------------------------------
        print("\n[3/3] Creating schedules...")
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        total_schedules = 0

        for subject_code, subject_name, year_level, days, start, end in SCHEDULE_DEFS:
            room_idx = SUBJECT_ROOM_MAP[subject_code]
            room = rooms[room_idx]

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
                    target_course="BSCPE",
                    target_year_level=year_level,
                    is_active=True,
                )
                db.add(schedule)
                db.flush()
                total_schedules += 1
                print(f"  {subject_code} (Year {year_level}) — {day_names[day_idx]} "
                      f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} in {room.name}")

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
        print(f"  Email:      admin@jrmsu.edu.ph")
        print(f"  Password:   admin123")
        print(f"\nFaculty Login:")
        print(f"  Email:      faculty@gmail.com")
        print(f"  Password:   password123")
        print(f"\nRooms: {len(rooms)}")
        for r in rooms:
            print(f"  {r.name} ({r.building}) — ID: {r.id}")
        print(f"\nSchedules: {total_schedules} total")
        print(f"  CPE 401 (Year 4): Every day 00:00-23:59 in Room 301 (24/7 test)")
        print(f"  CPE 301 (Year 4): Every day 07:00-22:00 in Room 301")
        print(f"  CPE 201 (Year 3): Mon-Sat 08:00-10:00 in Room 202")
        print(f"  CPE 101 (Year 2): Mon-Sat 09:00-11:00 in Room 103")
        print(f"  GE 101  (Year 1): Mon-Sat 13:00-15:00 in Room 103")
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
