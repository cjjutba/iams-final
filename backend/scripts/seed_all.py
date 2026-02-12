"""
Full Development Seed Script

Runs the complete seed sequence for local development and thesis demonstration:
  1. seed_reference_data  — populates student_records + faculty_records
  2. seed_data            — creates faculty user, rooms, schedules (with auto-enrollment targeting)
  3. seed_content         — creates faculty notifications

After running this script you have:
  - 10 mock students in student_records (available for self-registration via mobile app)
  - 1 mock faculty in faculty_records
  - A faculty account (faculty@gmail.com / password123)
  - 3 rooms (Room 301, Room 202, Room 103) in Engineering Building
  - 13 schedules (4 subjects across all year levels, Mon-Fri patterns)
  - 5 faculty notifications

Students self-register via mobile app → auto-enrolled in matching schedules.

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

    print("\n" + "=" * 60)
    print("ALL SEED DATA COMPLETE")
    print("=" * 60)
    print("\nReady for development/testing.")
    print("Student IDs available for self-registration:")
    print("  Year 4: 21-A-11111, 21-A-22222, 21-A-33333  (DOB: 01/01/2003, 02/02/2003, 03/03/2003)")
    print("  Year 3: 22-A-44444, 22-A-55555, 22-A-66666  (DOB: 04/04/2004, 05/05/2004, 06/06/2004)")
    print("  Year 2: 23-A-77777, 23-A-88888              (DOB: 07/07/2005, 08/08/2005)")
    print("  Year 1: 24-A-99999, 24-A-00000              (DOB: 09/09/2006, 10/10/2006)")
    print("\nFaculty login: faculty@gmail.com / password123")


if __name__ == "__main__":
    main()
