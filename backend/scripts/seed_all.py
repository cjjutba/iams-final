"""
Full Development Seed Script

Runs the complete seed sequence for local development and thesis demonstration:
  1. seed_reference_data  — populates student_records + faculty_records
  2. seed_data            — creates faculty user, rooms, schedules (with auto-enrollment targeting)
  3. seed_content         — creates faculty notifications
  4. seed_simulation      — creates student users, enrollments, attendance history, etc.

After running this script you have:
  - 10 mock students in student_records (available for self-registration via mobile app)
  - 1 mock faculty in faculty_records
  - A faculty account (faculty@gmail.com / password123)
  - 10 student accounts (all with password123, linked to Supabase Auth)
  - 3 rooms (Room 301, Room 202, Room 103) in Engineering Building
  - 13 schedules (4 subjects across all year levels, Mon-Fri patterns)
  - 34 enrollments (students matched to schedules by year level)
  - ~136 attendance records (4 weeks of history)
  - ~750 presence logs, ~7 early leave events, ~75 notifications

Run from backend directory:
    python -m scripts.seed_all

All sub-scripts are idempotent so this is safe to run multiple times.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_reference_data import seed_reference_data
from scripts.seed_data import seed
from scripts.seed_content import seed_content
from scripts.seed_simulation import seed_simulation


def main():
    print("\n" + "=" * 60)
    print("IAMS - Full Development Seed")
    print("=" * 60)

    print("\n>>> Step 1: Reference Data (student_records + faculty_records)")
    seed_reference_data()

    print("\n>>> Step 2: Operational Data (faculty user, rooms, schedules)")
    seed()

    print("\n>>> Step 3: Content Data (faculty notifications)")
    seed_content()

    print("\n>>> Step 4: Simulation Data (students, enrollments, attendance)")
    seed_simulation()

    print("\n" + "=" * 60)
    print("ALL SEED DATA COMPLETE")
    print("=" * 60)
    print("\nReady for development/testing.")
    print("\nFaculty login: faculty@gmail.com / password123")
    print("\nStudent logins (all use password123):")
    print("  Year 4: 21-A-11111 (Christian Jerald Jutba), 21-A-22222, 21-A-33333")
    print("  Year 3: 22-A-44444, 22-A-55555, 22-A-66666")
    print("  Year 2: 23-A-77777, 23-A-88888")
    print("  Year 1: 24-A-99999, 24-A-00000")


if __name__ == "__main__":
    main()
