"""
IAMS VPS test-block patch — additive seeder.

Inserts the 70 IAMS test-block schedules (5 ~5h windows × 7 days × 2 rooms)
into the VPS postgres, IDEMPOTENTLY. Safe to run repeatedly:

  - Pre-existing test-block rows are detected by `subject_code LIKE 'EB22_-%-%'`
    and skipped on a second run.
  - The script touches only the `schedules` table. Faculty users, rooms,
    real classes, and system_settings are read-only here.
  - Failure rolls back the transaction.

This exists alongside `seed_vps_minimal.py` because that script wipes-then-
seeds the entire VPS DB. When you only want to *add* the test blocks
without wiping faculty / real schedules / sessions in flight, run this
instead:

    docker cp backend/scripts/seed_vps_test_blocks.py iams-api-gateway-vps:/app/scripts/
    docker exec iams-api-gateway-vps python -m scripts.seed_vps_test_blocks

The on-prem Mac uses the same TEST_BLOCK_WINDOWS layout via
`scripts/seed_data._seed_test_blocks`, so this script reads from the same
constants — both backends generate the same 70 rows.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Room, Schedule, User, UserRole

from scripts.seed_data import (
    ACADEMIC_YEAR,
    SEMESTER,
    TEST_BLOCK_DAY_NAMES,
    TEST_BLOCK_EARLY_LEAVE_TIMEOUT_MIN,
    TEST_BLOCK_ROOMS,
    TEST_BLOCK_WINDOWS,
)


def _existing_test_block_codes(db) -> set[str]:
    """Subject_codes that already match the test-block pattern.

    The wildcard matches `EB226-MON-0000` / `EB227-FRI-2000` etc. — anything
    starting with `EB22<digit>-`. Using SQL LIKE (not Python startswith) so
    we don't pull every schedule across the wire.
    """
    rows = db.execute(
        select(Schedule.subject_code).where(
            Schedule.subject_code.like("EB226-%")
            | Schedule.subject_code.like("EB227-%")
        )
    ).all()
    return {r[0] for r in rows}


def patch() -> None:
    print("=" * 70)
    print("  IAMS VPS Test-Block Patch (additive — no wipe)")
    print("=" * 70)

    init_db()
    db = SessionLocal()

    try:
        # Look up the test faculty + rooms. These must already exist; the
        # script intentionally does not create them, because that's the job
        # of seed_vps_minimal which already ran.
        faculty_map: dict[str, User] = {}
        for room_name, faculty_email in TEST_BLOCK_ROOMS:
            user = db.execute(
                select(User).where(
                    User.email == faculty_email,
                    User.role == UserRole.FACULTY,
                )
            ).scalar_one_or_none()
            if user is None:
                raise RuntimeError(
                    f"Faculty user {faculty_email!r} not found on this VPS. "
                    f"Run scripts.seed_vps_minimal first."
                )
            faculty_map[faculty_email] = user

        room_map: dict[str, Room] = {}
        for room_name, _faculty_email in TEST_BLOCK_ROOMS:
            room = db.execute(
                select(Room).where(Room.name == room_name)
            ).scalar_one_or_none()
            if room is None:
                raise RuntimeError(
                    f"Room {room_name!r} not found on this VPS. "
                    f"Run scripts.seed_vps_minimal first."
                )
            room_map[room_name] = room

        existing = _existing_test_block_codes(db)
        print(f"\nExisting EB22*-*-* schedules on VPS: {len(existing)}")

        added = 0
        skipped = 0
        for room_name, faculty_email in TEST_BLOCK_ROOMS:
            faculty = faculty_map[faculty_email]
            room = room_map[room_name]
            for day_idx in range(7):
                day_short = TEST_BLOCK_DAY_NAMES[day_idx]
                for hour_label, start_t, end_t in TEST_BLOCK_WINDOWS:
                    code = f"{room_name}-{day_short}-{hour_label}"
                    if code in existing:
                        skipped += 1
                        continue
                    db.add(Schedule(
                        subject_code=code,
                        subject_name=(
                            f"IAMS Test {room_name} {day_short} "
                            f"({start_t.strftime('%H:%M')}-"
                            f"{end_t.strftime('%H:%M')})"
                        ),
                        faculty_id=faculty.id,
                        room_id=room.id,
                        day_of_week=day_idx,
                        start_time=start_t,
                        end_time=end_t,
                        semester=SEMESTER,
                        academic_year=ACADEMIC_YEAR,
                        target_course="BSCPE",
                        target_year_level=4,
                        early_leave_timeout_minutes=(
                            TEST_BLOCK_EARLY_LEAVE_TIMEOUT_MIN
                        ),
                        is_active=True,
                    ))
                    added += 1

        db.commit()

        print(f"\nInserted: {added} new test-block schedules")
        print(f"Skipped:  {skipped} (already existed — idempotent re-run)")
        print()
        print("Per-room breakdown after patch:")
        for room_name, _faculty_email in TEST_BLOCK_ROOMS:
            count = db.execute(
                select(Schedule).where(
                    Schedule.subject_code.like(f"{room_name}-%"),
                )
            ).all()
            print(f"  {room_name}: {len(count)} test blocks")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    patch()
