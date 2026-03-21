"""
Seed Content Data for IAMS Backend

Creates faculty-only notifications for the default faculty user.
Student data (attendance, presence logs, etc.) is created dynamically
when students register and attend classes via the automated system.

Run from backend directory:
    python -m scripts.seed_content

Prerequisites: Run seed_data first (python -m scripts.seed_data)
This script is idempotent -- it checks before inserting.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import User, Notification
from app.config import logger


def seed_content():
    """
    Seed faculty-only content data.

    Creates notifications for the default faculty user.
    No student-dependent data is created — that happens dynamically
    when students register and attend classes.
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Content Data")
        print("=" * 60)

        # ------------------------------------------------------------------
        # Find existing faculty user
        # ------------------------------------------------------------------
        faculty = db.query(User).filter(User.email == "faculty@gmail.com").first()

        if not faculty:
            print("\nERROR: Faculty user not found. Run 'python -m scripts.seed_data' first.")
            return

        print(f"\nFaculty: {faculty.first_name} {faculty.last_name} ({faculty.id})")

        # ------------------------------------------------------------------
        # Idempotency check
        # ------------------------------------------------------------------
        existing_notifs = (
            db.query(Notification)
            .filter(Notification.user_id == faculty.id)
            .count()
        )

        if existing_notifs > 0:
            print(f"\nContent data already exists ({existing_notifs} notifications). Skipping...")
            return

        # ------------------------------------------------------------------
        # Create Faculty Notifications
        # ------------------------------------------------------------------
        print("\n[1/1] Creating faculty notifications...")

        notifications_data = [
            {
                "user_id": faculty.id,
                "title": "Welcome to IAMS",
                "message": "Your faculty account has been set up. Students will appear in your class roster as they register through the mobile app.",
                "type": "system",
                "read": False,
                "reference_type": None,
                "created_at": datetime(2026, 2, 10, 8, 0),
            },
            {
                "user_id": faculty.id,
                "title": "Classes Configured",
                "message": "Your class schedules have been configured for rooms EB226 and EB227 in the Engineering Building. Subjects include CpE 121, CpE 115, CpE 120, CpE 113, CpE 322, CpE 324, CpE 326, CpE 421, and ES 112.",
                "type": "system",
                "read": True,
                "read_at": datetime(2026, 2, 10, 9, 0),
                "reference_type": "schedule",
                "created_at": datetime(2026, 2, 10, 8, 30),
            },
            {
                "user_id": faculty.id,
                "title": "System Ready",
                "message": "The IAMS attendance monitoring system is ready. The Raspberry Pi camera in EB227 will automatically detect and track student attendance during class hours.",
                "type": "system",
                "read": False,
                "reference_type": None,
                "created_at": datetime(2026, 2, 11, 7, 0),
            },
            {
                "user_id": faculty.id,
                "title": "Student Registration Open",
                "message": "Students can now register via the IAMS mobile app using their university Student ID. Registered students will be auto-enrolled in your classes based on their course and year level.",
                "type": "system",
                "read": False,
                "reference_type": None,
                "created_at": datetime(2026, 2, 11, 8, 0),
            },
            {
                "user_id": faculty.id,
                "title": "Camera Setup Reminder",
                "message": "Please ensure the Raspberry Pi camera is positioned correctly in EB227 and connected to the local network. Contact the admin if you need assistance.",
                "type": "alert",
                "read": False,
                "reference_type": None,
                "created_at": datetime(2026, 2, 12, 7, 0),
            },
        ]

        for notif_data in notifications_data:
            db.add(Notification(**notif_data))

        db.flush()
        print(f"  Created {len(notifications_data)} faculty notifications")

        # ------------------------------------------------------------------
        # Commit everything
        # ------------------------------------------------------------------
        db.commit()
        logger.info("Content seed data committed successfully")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("CONTENT SEED COMPLETE")
        print("=" * 60)
        print(f"\nFaculty Notifications: {len(notifications_data)}")
        for n in notifications_data:
            status = "read" if n.get("read") else "unread"
            print(f"  [{status}] {n['title']}")

    except Exception as e:
        db.rollback()
        logger.error(f"Content seed failed: {e}")
        print(f"\nERROR: Content seed failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_content()
