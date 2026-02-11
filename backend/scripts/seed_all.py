"""
Full Development Seed Script

Runs the complete seed sequence for local development and integration testing:
  1. seed_reference_data  — populates student_records + faculty_records
  2. seed_data            — creates test users, rooms, schedules, enrollments

After running this script you have:
  - 10 mock students in student_records (available for registration)
  - 3 mock faculty in faculty_records
  - A fully-registered student account (cjjutbaofficial@gmail.com / password123)
  - A faculty account          (faculty@gmail.com / password123)
  - Room 301 + CPE 301 Mon-Fri schedules
  - Student enrolled in all 5 schedules

Run from backend directory:
    python -m scripts.seed_all

Both sub-scripts are idempotent so this is safe to run multiple times.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_reference_data import seed_reference_data
from scripts.seed_data import seed


def main():
    print("\n" + "=" * 60)
    print("IAMS - Full Development Seed")
    print("=" * 60)

    print("\n>>> Step 1: Reference Data (student_records + faculty_records)")
    seed_reference_data()

    print("\n>>> Step 2: Operational Data (users, rooms, schedules, enrollments)")
    seed()

    print("\n" + "=" * 60)
    print("ALL SEED DATA COMPLETE")
    print("=" * 60)
    print("\nReady for development/testing.")
    print("Student IDs available for registration: see seed_reference_data output above.")


if __name__ == "__main__":
    main()
