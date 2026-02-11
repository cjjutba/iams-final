"""
Update Student Password Script

Updates the password for the seed student (21-A-02177) to the new password.

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
    """Update the password for student 21-A-02177."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Updating Student Password")
        print("=" * 60)

        # Find the student
        student = db.query(User).filter(
            User.student_id == "21-A-02177"
        ).first()

        if not student:
            print("\nERROR: Student 21-A-02177 not found in database.")
            print("Please run the seed script first: python -m scripts.seed_data")
            return

        print(f"\nFound student: {student.first_name} {student.last_name}")
        print(f"Email: {student.email}")
        print(f"Student ID: {student.student_id}")

        # Update password
        new_password = "password123"
        student.password_hash = hash_password(new_password)

        db.commit()
        logger.info(f"Password updated for student {student.student_id}")

        print("\n" + "=" * 60)
        print("PASSWORD UPDATE COMPLETE")
        print("=" * 60)
        print(f"\nNew Login Credentials:")
        print(f"  Email:      {student.email}")
        print(f"  Student ID: {student.student_id}")
        print(f"  Password:   {new_password}")

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
