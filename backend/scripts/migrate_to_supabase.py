"""
Migrate Existing Users to Supabase Auth

Migrates all local-only users (those without a supabase_user_id) into
Supabase Auth by creating corresponding auth accounts via the Admin API.

For each user the script:
  1. Creates a Supabase Auth account with a temporary password
  2. Marks the Supabase account as email-confirmed (existing users are trusted)
  3. Updates the local users row: supabase_user_id, email_verified, email_verified_at

Individual failures do NOT abort the entire run -- the script logs them and
continues with the next user. A summary is printed at the end.

Run from backend directory:
    python -m scripts.migrate_to_supabase              # live run
    python -m scripts.migrate_to_supabase --dry-run    # preview only
"""

import argparse
import secrets
import sys
import traceback
import uuid as uuid_mod
from datetime import datetime
from pathlib import Path

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import logger
from app.database import SessionLocal
from app.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_temp_password(length: int = 24) -> str:
    """
    Generate a cryptographically random temporary password.

    Users will need to use Supabase's password-reset flow to set their own
    password after migration.
    """
    return secrets.token_urlsafe(length)


def create_supabase_auth_user(supabase_client, user: User, temp_password: str) -> str:
    """
    Create a user in Supabase Auth via the Admin API.

    Args:
        supabase_client: Authenticated Supabase admin client.
        user: Local User model instance.
        temp_password: Temporary password to assign.

    Returns:
        The Supabase user ID (string UUID).

    Raises:
        Exception on any Supabase API error.
    """
    user_metadata = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value,
    }
    if user.student_id:
        user_metadata["student_id"] = user.student_id

    response = supabase_client.auth.admin.create_user({
        "email": user.email,
        "password": temp_password,
        "email_confirm": True,  # Existing users are already verified
        "user_metadata": user_metadata,
    })

    return response.user.id


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def migrate(dry_run: bool = False):
    """
    Migrate all local-only users to Supabase Auth.

    Args:
        dry_run: If True, list what would happen without making changes.
    """
    # Lazy-import the Supabase client so --dry-run works even without valid
    # Supabase credentials (the client is only needed for live runs).
    supabase_client = None
    if not dry_run:
        from app.services.supabase_client import get_supabase_admin
        supabase_client = get_supabase_admin()

    db = SessionLocal()

    try:
        print("=" * 60)
        if dry_run:
            print("IAMS - Migrate Users to Supabase Auth  [DRY RUN]")
        else:
            print("IAMS - Migrate Users to Supabase Auth")
        print("=" * 60)

        # Query users that have NOT been linked to Supabase yet
        users_to_migrate = (
            db.query(User)
            .filter(User.supabase_user_id.is_(None))
            .order_by(User.created_at)
            .all()
        )

        total = len(users_to_migrate)

        if total == 0:
            print("\nNo users require migration. All users already have a supabase_user_id.")
            return

        print(f"\nFound {total} user(s) to migrate:\n")

        succeeded = 0
        failed = 0
        failures: list[dict] = []

        for idx, user in enumerate(users_to_migrate, start=1):
            label = f"[{idx}/{total}]"
            print(f"  {label} {user.email} (role={user.role.value}, id={user.id})")

            if dry_run:
                print(f"         -> Would create Supabase Auth account")
                succeeded += 1
                continue

            temp_password = generate_temp_password()

            try:
                supabase_uid = create_supabase_auth_user(
                    supabase_client, user, temp_password
                )

                # Update local record
                user.supabase_user_id = uuid_mod.UUID(str(supabase_uid))
                user.email_verified = True
                user.email_verified_at = datetime.utcnow()
                db.flush()

                logger.info(
                    f"Migrated user {user.email} -> supabase_user_id={supabase_uid}"
                )
                print(f"         -> OK  supabase_user_id={supabase_uid}")
                succeeded += 1

            except Exception as exc:
                error_msg = str(exc)
                logger.error(
                    f"Failed to migrate user {user.email}: {error_msg}"
                )
                print(f"         -> FAILED: {error_msg}")
                failures.append({
                    "email": user.email,
                    "user_id": str(user.id),
                    "error": error_msg,
                })
                failed += 1

                # Expunge the dirty object so the session stays usable for
                # subsequent users.
                db.expire(user)

        # Commit all successful updates in one transaction
        if not dry_run and succeeded > 0:
            db.commit()
            logger.info(
                f"Migration committed: {succeeded} succeeded, {failed} failed"
            )

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        print("\n" + "=" * 60)
        if dry_run:
            print("DRY RUN SUMMARY")
        else:
            print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"\n  Total users processed : {total}")
        print(f"  Succeeded             : {succeeded}")
        print(f"  Failed                : {failed}")

        if failures:
            print(f"\n  Failed users:")
            for f in failures:
                print(f"    - {f['email']} (id={f['user_id']})")
                print(f"      Error: {f['error']}")

        if not dry_run and succeeded > 0:
            print(
                "\nNOTE: Migrated users were assigned temporary passwords. "
                "They should use the 'Forgot Password' flow to set a new "
                "password on first login."
            )

        if dry_run:
            print("\nNo changes were made (dry run).")

    except Exception as exc:
        db.rollback()
        logger.error(f"Migration aborted: {exc}")
        print(f"\nFATAL ERROR: Migration aborted: {exc}")
        traceback.print_exc()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate existing IAMS users to Supabase Auth."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which users would be migrated without making changes.",
    )
    args = parser.parse_args()

    migrate(dry_run=args.dry_run)
