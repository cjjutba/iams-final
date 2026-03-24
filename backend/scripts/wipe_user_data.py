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
  - FAISS index file       (data/faiss/faces.index)

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
from app.config import settings, logger


def _delete_faiss_index() -> bool:
    """Delete the FAISS index file so it's rebuilt fresh on next startup."""
    faiss_path = Path(__file__).resolve().parents[1] / settings.FAISS_INDEX_PATH
    if faiss_path.exists():
        faiss_path.unlink()
        print(f"  Deleted FAISS index: {faiss_path}")
        return True
    else:
        print(f"  FAISS index not found (already clean): {faiss_path}")
        return False


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

        # STEP 1: Get or create the default faculty + admin accounts FIRST
        # (We need faculty to reassign schedules before deleting old users)
        print("\n[1/3] Preparing default accounts...")

        # --- Faculty account ---
        existing_faculty = db.query(User).filter(User.email == "faculty@gmail.com").first()

        if existing_faculty:
            new_faculty = existing_faculty
            new_faculty.password_hash = hash_password("password123")
            new_faculty.is_active = True
            new_faculty.email_verified = True
            db.flush()
            print(f"  Using existing: faculty@gmail.com (ID: {new_faculty.id})")
        else:
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

        # --- Admin account ---
        existing_admin = db.query(User).filter(User.email == "admin@admin.com").first()

        if existing_admin:
            new_admin = existing_admin
            new_admin.password_hash = hash_password("admin123")
            new_admin.is_active = True
            new_admin.email_verified = True
            db.flush()
            print(f"  Using existing: admin@admin.com (ID: {new_admin.id})")
        else:
            new_admin = User(
                email="admin@admin.com",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                first_name="System",
                last_name="Admin",
                is_active=True,
                email_verified=True,
            )
            db.add(new_admin)
            db.flush()
            print(f"  Created: admin@admin.com (ID: {new_admin.id})")

        keep_user_ids = {new_faculty.id, new_admin.id}

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
                # Keep both faculty and admin accounts
                count = db.query(model).filter(model.id.notin_(keep_user_ids)).delete(synchronize_session=False)
            else:
                count = db.query(model).delete(synchronize_session=False)
            total_deleted += count
            print(f"  Deleted {count:>4} rows from {table_name}")

        db.flush()

        print(f"\n[3/3] Finalizing changes...")
        db.commit()
        logger.info("User data wiped successfully")

        # STEP 4: Delete FAISS index file for a clean start
        faiss_deleted = _delete_faiss_index()

        print("\n" + "=" * 60)
        print("WIPE COMPLETE")
        print("=" * 60)
        print(f"\nTotal DB rows deleted: {total_deleted}")
        print(f"FAISS index deleted: {faiss_deleted}")
        print("\nReference data (student_records, faculty_records, rooms, schedules) preserved.")
        print(f"All {schedule_count} schedules have been reassigned to the new faculty account.")
        print("\nDefault Admin Account (web dashboard):")
        print("  Email:    admin@admin.com")
        print("  Password: admin123")
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
