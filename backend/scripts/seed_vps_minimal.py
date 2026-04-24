"""
IAMS VPS Minimal Seed Script

Seeds the VPS postgres (behind deploy/docker-compose.vps.yml) with ONLY
the data the faculty mobile app needs:

  - Faculty records (faculty_records table)
  - Faculty user accounts (users table — role=FACULTY, password123)
  - Admin user account (for occasional VPS-side admin debugging)
  - Rooms (rooms table — needed for stream_key lookup)
  - Real faculty schedules (schedules table — subset of SCHEDULE_DEFS)
  - System settings (authoritative constants the faculty app reads)

What is INTENTIONALLY NOT seeded on the VPS:

  - Student user accounts + records (PII stays on-campus)
  - Face embeddings / FAISS index (never leave the Mac)
  - Enrollments (students and faculty both live in two worlds; enrollment
    only matters where attendance is recorded = on-prem Mac)
  - Attendance records, presence logs, early-leave events (monitoring is
    admin-portal-on-LAN only)
  - Rolling 30-min test sessions (dev/thesis-only, 672 rows of no value
    to the faculty app's "today's classes" list)
  - Notifications (notification router disabled on VPS)

The seed reuses FACULTY_RECORDS / FACULTY_USERS / ROOM_DEFS / SCHEDULE_DEFS
from scripts/seed_data.py so changing a faculty name / adding a schedule
is a one-line edit in ONE place — both Mac and VPS pick it up.

Usage (on the VPS):
    docker compose -f deploy/docker-compose.vps.yml exec -T api-gateway \\
        python -m scripts.seed_vps_minimal

Or via deploy/deploy.sh vps, which runs this automatically on first deploy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.config import logger
from app.database import SessionLocal, init_db
from app.models import (
    FacultyRecord,
    Room,
    Schedule,
    SystemSetting,
    User,
    UserRole,
)
from app.utils.security import hash_password

# Reuse the canonical data from the full seed so the two stay in sync.
from scripts.seed_data import (
    ACADEMIC_YEAR,
    FACULTY_RECORDS,
    FACULTY_USERS,
    ROOM_DEFS,
    SCHEDULE_DEFS,
    SEMESTER,
    SYSTEM_SETTINGS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Wipe (only the tables we touch — much narrower than seed_data's TRUNCATE)
# ═══════════════════════════════════════════════════════════════════════════════


def _wipe_vps_tables(db) -> None:
    """Truncate only the tables this script owns.

    We DO NOT wipe `refresh_tokens`, `face_*`, `enrollments`, `attendance_*`,
    `presence_*`, etc. — those tables don't exist in practice on the VPS
    (no face registration, no attendance, no enrollments happen here), but
    if some earlier deploy left stray rows we don't care about them.
    """
    print("\n[1/5] Wiping VPS-owned tables (faculty + schedules + rooms + settings)...")
    db.execute(text("SET session_replication_role = 'replica'"))
    db.execute(text(
        """
        TRUNCATE TABLE
            schedules,
            faculty_records,
            system_settings,
            rooms
        CASCADE
        """
    ))
    # Delete only faculty + admin users — if a student somehow ended up on the
    # VPS (e.g. a misconfigured earlier deploy) leave them alone; they'll be
    # dead data the faculty app never queries.
    #
    # NOTE: the `userrole` Postgres enum labels are UPPERCASE (FACULTY/ADMIN/
    # STUDENT) because SQLAlchemy serialises Python enum `.name` not `.value`
    # when writing to a native enum column. Lowercase literals here would
    # fail with `invalid input value for enum userrole` — see git history
    # 2026-04-22 for the one-off bug that caught this.
    db.execute(text(
        """
        DELETE FROM users
         WHERE role IN ('FACULTY', 'ADMIN')
        """
    ))
    db.execute(text("SET session_replication_role = 'origin'"))
    db.flush()
    print("  Wiped.")


# ═══════════════════════════════════════════════════════════════════════════════
# Seeders — parallel to seed_data.py helpers but without student/face/attendance
# ═══════════════════════════════════════════════════════════════════════════════


def _seed_faculty_records(db) -> None:
    """Seed faculty_records table (same shape as local)."""
    print("\n[2/5] Seeding faculty records...")
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
    """Seed faculty user accounts + one admin. Same credentials as local.

    The VPS uses a DIFFERENT SECRET_KEY than local, so tokens minted here are
    only valid against this backend. But passwords are identical so faculty
    log in the same way (password123).
    """
    print("\n[3/5] Creating user accounts...")
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
    """Seed rooms (needed for stream_key lookup in faculty app)."""
    print("\n[4/5] Creating rooms...")
    room_map: dict[str, Room] = {}
    for name, building, capacity, camera_endpoint, stream_key in ROOM_DEFS:
        room = Room(
            name=name,
            building=building,
            capacity=capacity,
            # Overwrite the rtsp://mediamtx:8554/* endpoint — the VPS has no
            # mediamtx-internal DNS name visible from this API; the faculty
            # app derives the WHEP URL from stream_key only, so the endpoint
            # value is cosmetic here. Kept non-empty for DB not-null checks.
            camera_endpoint=f"rtsp://167.71.217.44:8554/{stream_key}",
            stream_key=stream_key,
            is_active=True,
        )
        db.add(room)
        db.flush()
        room_map[name] = room
        print(f"  {name}: stream_key={stream_key}")

    return room_map


def _seed_schedules(db, faculty_map: dict[str, User], room_map: dict[str, Room]) -> int:
    """Seed REAL faculty schedules only — no rolling 30-min test sessions.

    The VPS-side faculty app doesn't need the 672 rolling dev sessions;
    faculty see their real Mon/Wed/Fri classes, tap one, watch it.
    """
    print("\n[5/5] Creating schedules (real faculty only, no rolling test slots)...")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    total = 0
    for (subj_code, subj_name, year_level, target_course,
         days, start, end, room_name, faculty_email) in SCHEDULE_DEFS:
        faculty = faculty_map[faculty_email]
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
    """Seed system settings (same keys as local — faculty app reads a subset)."""
    for key, value in SYSTEM_SETTINGS:
        db.add(SystemSetting(key=key, value=value))
    db.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════


def seed() -> None:
    print("=" * 70)
    print("  IAMS VPS Minimal Seed")
    print("  Target: public VPS (167.71.217.44) postgres")
    print("  Policy: faculty + schedules + rooms only — no student data")
    print("=" * 70)

    init_db()
    db = SessionLocal()

    try:
        _wipe_vps_tables(db)
        _seed_faculty_records(db)
        faculty_map, _admin = _seed_users(db)
        room_map = _seed_rooms(db)
        schedule_count = _seed_schedules(db, faculty_map, room_map)
        _seed_system_settings(db)

        db.commit()

        print("\n" + "=" * 70)
        print("  VPS seed complete")
        print("=" * 70)
        print(f"  Faculty records:  {len(FACULTY_RECORDS)}")
        print(f"  Faculty users:    {len(FACULTY_USERS)} (password: password123)")
        print(f"  Admin users:      1 (admin@admin.com / 123)")
        print(f"  Rooms:            {len(ROOM_DEFS)}")
        print(f"  Schedules:        {schedule_count}")
        print(f"  System settings:  {len(SYSTEM_SETTINGS)}")
        print("")
        print("  Test faculty login:")
        print("    curl -X POST http://167.71.217.44/api/v1/auth/login \\")
        print("      -H 'Content-Type: application/json' \\")
        print("      -d '{\"identifier\":\"faculty.eb226@gmail.com\",\"password\":\"password123\"}'")
        print("")
    except Exception:
        db.rollback()
        logger.exception("VPS seed failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
