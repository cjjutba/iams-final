"""
Update Faculty Password Script

Updates the password for all faculty users to the new password.

Run from backend directory:
    python -m scripts.update_faculty_password
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
    """Update the password for faculty.eb226@gmail.com."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Updating Faculty Password")
        print("=" * 60)

        # Find the faculty user
        faculty = db.query(User).filter(
            User.email == "faculty.eb226@gmail.com"
        ).first()

        if not faculty:
            print("\nERROR: Faculty user (faculty.eb226@gmail.com) not found in database.")
            print("Please run the seed script first: python -m scripts.seed_data")
            return

        print(f"\nFound faculty: {faculty.first_name} {faculty.last_name}")
        print(f"Email: {faculty.email}")
        print(f"Role: {faculty.role}")

        # Update password
        new_password = "password123"
        faculty.password_hash = hash_password(new_password)

        db.commit()
        logger.info(f"Password updated for faculty {faculty.email}")

        print("\n" + "=" * 60)
        print("PASSWORD UPDATE COMPLETE")
        print("=" * 60)
        print(f"\nNew Login Credentials:")
        print(f"  Email:    {faculty.email}")
        print(f"  Password: {new_password}")

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
