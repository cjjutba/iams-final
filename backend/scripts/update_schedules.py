"""
Update Schedules Script

Drops all existing schedules and re-creates them using the current
SCHEDULE_DEFS from seed_data.py. Keeps rooms and faculty intact.

Run from backend directory:
    python -m scripts.update_schedules
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import User, UserRole, Room, Schedule
from app.models.enrollment import Enrollment
from app.config import logger
from scripts.seed_data import SCHEDULE_DEFS, SUBJECT_ROOM_MAP, ROOM_DEFS


def update_schedules():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Update Schedules")
        print("=" * 60)

        # Find the faculty user
        faculty = db.query(User).filter(
            User.email == "faculty@gmail.com",
            User.role == UserRole.FACULTY,
        ).first()

        if not faculty:
            print("ERROR: Faculty user (faculty@gmail.com) not found. Run seed_data first.")
            return

        # Build room lookup by name to match ROOM_DEFS order
        # SUBJECT_ROOM_MAP indexes into ROOM_DEFS, not alphabetical DB order
        all_rooms = db.query(Room).all()
        room_by_name = {r.name: r for r in all_rooms}

        # Build ordered list matching ROOM_DEFS order
        rooms = []
        for name, _, _, _ in ROOM_DEFS:
            if name not in room_by_name:
                print(f"ERROR: Room '{name}' not found in DB. Run seed_data first.")
                return
            rooms.append(room_by_name[name])

        print(f"\nFaculty: {faculty.email} (ID: {faculty.id})")
        print(f"Rooms: {len(rooms)}")
        for i, r in enumerate(rooms):
            print(f"  [{i}] {r.name} (ID: {r.id})")

        # Delete dependent records first (FK constraints)
        from app.models import AttendanceRecord, PresenceLog, EarlyLeaveEvent
        for model, name in [
            (PresenceLog, "presence_logs"),
            (EarlyLeaveEvent, "early_leave_events"),
            (AttendanceRecord, "attendance_records"),
            (Enrollment, "enrollments"),
        ]:
            count = db.query(model).count()
            if count > 0:
                db.query(model).delete(synchronize_session=False)
                print(f"Deleted {count} {name}")

        # Delete existing schedules
        old_count = db.query(Schedule).count()
        db.query(Schedule).delete(synchronize_session=False)
        print(f"Deleted {old_count} old schedules")

        # Create new schedules from SCHEDULE_DEFS
        print("\nCreating new schedules...")
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        total = 0

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
                total += 1
                print(f"  {subject_code} (Year {year_level}) — {day_names[day_idx]} "
                      f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} in {room.name}")

        db.commit()
        logger.info(f"Updated schedules: {old_count} removed, {total} created")

        print(f"\n{'=' * 60}")
        print(f"UPDATE COMPLETE: {total} schedules created")
        print(f"{'=' * 60}")
        print(f"\nNote: Students will need to re-register or be re-enrolled")
        print(f"to be linked to the new schedules.")

    except Exception as e:
        db.rollback()
        logger.error(f"Schedule update failed: {e}")
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    update_schedules()
