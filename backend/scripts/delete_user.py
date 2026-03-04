"""
Delete User Script

Removes a user account by student ID or email for testing purposes.

Usage:
    python -m scripts.delete_user 21-A-012345
    python -m scripts.delete_user cjjutbaofficial@gmail.com
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import User
from sqlalchemy import or_


def delete_user(identifier: str) -> None:
    """Delete a user by student ID or email."""
    db = SessionLocal()

    try:
        # Try to find by student_id or email
        user = db.query(User).filter(
            or_(
                User.student_id == identifier.upper(),
                User.email == identifier.lower()
            )
        ).first()

        if not user:
            print(f"❌ User not found: {identifier}")
            return

        print(f"\n🔍 Found user:")
        print(f"  ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Name: {user.first_name} {user.last_name}")
        print(f"  Role: {user.role}")
        if user.student_id:
            print(f"  Student ID: {user.student_id}")

        confirm = input(f"\n⚠️  Delete this user? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            return

        db.delete(user)
        db.commit()
        print(f"✅ User deleted successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.delete_user <student_id_or_email>")
        print("Example: python -m scripts.delete_user 21-A-012345")
        sys.exit(1)

    identifier = sys.argv[1]
    delete_user(identifier)
