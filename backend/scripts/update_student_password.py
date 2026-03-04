"""
Update Student Password Script

Updates the password for seed students to the new password.

Run from backend directory:
    python -m scripts.update_student_password
"""

import sys
from pathlib import Path

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import User
from app.utils.security import hash_password
from app.config import logger


def update_password():
    """Update the password for all seed students."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Updating Student Password")
        print("=" * 60)

        # Find all student users
        students = db.query(User).filter(
            User.role == "student",
            User.student_id.isnot(None),
        ).all()

        if not students:
            print("\nERROR: No student users found in database.")
            print("Please run the seed script first: python -m scripts.seed_all")
            return

        new_password = "password123"
        new_hash = hash_password(new_password)

        for student in students:
            student.password_hash = new_hash
            print(f"  Updated: {student.student_id} — {student.first_name} {student.last_name}")

        db.commit()
        logger.info(f"Password updated for {len(students)} students")

        print("\n" + "=" * 60)
        print("PASSWORD UPDATE COMPLETE")
        print("=" * 60)
        print(f"\nUpdated {len(students)} student(s) — password: {new_password}")

    except Exception as e:
        db.rollback()
        logger.error(f"Password update failed: {e}")
        print(f"\nERROR: Password update failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    update_password()
