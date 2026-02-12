"""
Wipe User Data Script

Deletes all user-generated / transactional data from the database and
re-creates only the default faculty account. Reference data (student_records,
faculty_records) and school configuration (rooms, schedules) are preserved.

Use this to start a fresh pilot-test run without having to re-import
school data or reconfigure rooms and schedules.

What is DELETED:
  - users                  (all registered app users)
  - face_registrations     (all face embeddings)
  - attendance_records     (all attendance history)
  - presence_logs          (all scan logs)
  - early_leave_events     (all early-leave detections)
  - enrollments            (all student-schedule links)
  - notifications          (all in-app notifications)

What is KEPT:
  - student_records        (school's official student registry)
  - faculty_records        (school's official faculty registry)
  - rooms                  (room/camera configuration)
  - schedules              (class schedule configuration)

After wiping, one default faculty account is created:
  Email:    faculty@gmail.com
  Password: password123

Run from backend directory:
    python -m scripts.wipe_user_data

WARNING: This is destructive. All registered users will need to re-register.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import (
    User, UserRole,
    FaceRegistration,
    AttendanceRecord,
    PresenceLog,
    EarlyLeaveEvent,
    Enrollment,
    Notification,
)
from app.utils.security import hash_password
from app.config import logger


def wipe_user_data(confirm: bool = False):
    """
    Wipe all user-generated data and re-seed default faculty.

    Args:
        confirm: Must be True to proceed (safety guard).
    """
    if not confirm:
        print("\n⚠  DRY RUN — pass confirm=True or run via __main__ to actually wipe.")
        return

    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Wipe User Data")
        print("=" * 60)
        print("\nThis will DELETE all registered users and transactional data.")

        # STEP 1: Get or create the new default faculty account FIRST
        # (We need this to reassign schedules before deleting old users)
        print("\n[1/3] Preparing new default faculty account...")
        existing_faculty = db.query(User).filter(User.email == "faculty@gmail.com").first()

        if existing_faculty:
            # Use the existing faculty account and update its password
            new_faculty = existing_faculty
            new_faculty.password_hash = hash_password("password123")
            new_faculty.is_active = True
            new_faculty.email_verified = True
            db.flush()
            print(f"  Using existing: faculty@gmail.com (ID: {new_faculty.id})")
        else:
            # Create a brand new faculty account
            new_faculty = User(
                email="faculty@gmail.com",
                password_hash=hash_password("password123"),
                role=UserRole.FACULTY,
                first_name="Faculty",
                last_name="User",
                phone="09000000000",
                is_active=True,
                email_verified=True,
            )
            db.add(new_faculty)
            db.flush()
            print(f"  Created: faculty@gmail.com (ID: {new_faculty.id})")

        # STEP 2: Reassign all schedules to the new faculty
        # (This removes the FK dependency on old faculty users)
        from app.models.schedule import Schedule
        schedule_count = db.query(Schedule).count()
        if schedule_count > 0:
            db.query(Schedule).update(
                {"faculty_id": new_faculty.id},
                synchronize_session=False
            )
            print(f"  Reassigned {schedule_count:>4} schedules to new faculty")
        db.flush()

        # STEP 3: Delete all transactional data and old users
        # Order matters — delete children before parents to respect FK constraints
        print("\n[2/3] Deleting transactional data and old users...")
        tables = [
            (PresenceLog,        "presence_logs"),
            (EarlyLeaveEvent,    "early_leave_events"),
            (AttendanceRecord,   "attendance_records"),
            (Enrollment,         "enrollments"),
            (Notification,       "notifications"),
            (FaceRegistration,   "face_registrations"),
            (User,               "users"),
        ]

        total_deleted = 0
        for model, table_name in tables:
            if model == User:
                # Only delete users that are NOT the new faculty we just created
                count = db.query(model).filter(model.id != new_faculty.id).delete(synchronize_session=False)
            else:
                count = db.query(model).delete(synchronize_session=False)
            total_deleted += count
            print(f"  Deleted {count:>4} rows from {table_name}")

        db.flush()

        print(f"\n[3/3] Finalizing changes...")
        db.commit()
        logger.info("User data wiped successfully")

        print("\n" + "=" * 60)
        print("WIPE COMPLETE")
        print("=" * 60)
        print(f"\nTotal rows deleted: {total_deleted}")
        print("\nReference data (student_records, faculty_records, rooms, schedules) preserved.")
        print(f"All {schedule_count} schedules have been reassigned to the new faculty account.")
        print("\nDefault Faculty Account:")
        print("  Email:    faculty@gmail.com")
        print("  Password: password123")
        print("\nStudents can now re-register using their student IDs from student_records.")

    except Exception as e:
        db.rollback()
        logger.error(f"Wipe failed: {e}")
        print(f"\nERROR: Wipe failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Wipe all user data and re-seed default faculty."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag to actually perform the wipe (safety guard).",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("\nWARNING: This will permanently delete all user data.")
        print("Run with --confirm to proceed:")
        print("  python -m scripts.wipe_user_data --confirm")
        sys.exit(0)

    wipe_user_data(confirm=True)
