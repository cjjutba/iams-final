"""
Full Development Seed Script

Runs the complete seed sequence for local development and thesis demonstration:
  1. seed_reference_data  — populates student_records + faculty_records
  2. seed_data            — creates faculty user, rooms, schedules (with auto-enrollment targeting)
  3. seed_content         — creates faculty notifications
  4. seed_simulation      — creates student users, enrollments, attendance history, etc.

Usage:
    python -m scripts.seed_all                # Full seed (includes simulation)
    python -m scripts.seed_all --no-sim       # Skip simulation (for testing registration flow)

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
    skip_sim = "--no-sim" in sys.argv

    print("\n" + "=" * 60)
    print("IAMS - Full Development Seed")
    print("=" * 60)

    print("\n>>> Step 1: Reference Data (student_records + faculty_records)")
    seed_reference_data()

    print("\n>>> Step 2: Operational Data (faculty user, rooms, schedules)")
    seed()

    print("\n>>> Step 3: Content Data (faculty notifications)")
    seed_content()

    if skip_sim:
        print("\n>>> Step 4: Simulation Data — SKIPPED (--no-sim)")
    else:
        print("\n>>> Step 4: Simulation Data (students, enrollments, attendance)")
        seed_simulation()

    print("\n" + "=" * 60)
    print("ALL SEED DATA COMPLETE")
    print("=" * 60)
    print("\nReady for development/testing.")
    print("\nFaculty login: faculty@gmail.com / password123")

    if skip_sim:
        print("\nStudent registration: use mobile app with a Student ID from seed_reference_data")
    else:
        print("\nStudent login (password123):")
        print("  21-A-02177 — Christian Jerald Jutba (cjjutbaofficial@gmail.com)")
        print("  21-A-01234 — Juhazelle Espela (hazelleespela@gmail.com)")


if __name__ == "__main__":
    main()
