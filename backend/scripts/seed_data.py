"""
Seed Data Script for IAMS Backend

Creates test data for development and thesis demonstration.
Populates the database with a student user, faculty user, room,
schedules (Mon-Fri), and enrollments linking the student to all schedules.

Run from backend directory:
    python -m scripts.seed_data

This script is idempotent -- it checks for existing seed data before inserting
and will skip gracefully if the data already exists.
"""

import sys
from pathlib import Path

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import time
from app.database import SessionLocal, engine, Base
from app.models import User, UserRole, Room, Schedule, Enrollment
from app.utils.security import hash_password
from app.config import logger


def seed():
    """
    Main seed function.

    Creates the following test data in a single transaction:
      1. Student user (Christian Jerald Jutba)
      2. Faculty user (pre-seeded account)
      3. Room (Room 301, Engineering Building)
      4. Schedules (CPE 301 Mon-Fri, 07:00-22:00)
      5. Enrollments (student enrolled in all 5 schedules)

    Uses db.flush() between operations to obtain generated IDs while
    keeping everything in one atomic transaction. Only commits at the end
    so it is all-or-nothing.
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Database")
        print("=" * 60)

        # ------------------------------------------------------------------
        # Idempotency check: skip if seed data already exists
        # ------------------------------------------------------------------
        existing_student = db.query(User).filter(
            User.student_id == "21-A-02177"
        ).first()

        if existing_student:
            print("\nSeed data already exists. Skipping...")
            print(f"  Student: {existing_student.email} (ID: {existing_student.id})")
            existing_faculty = db.query(User).filter(
                User.email == "faculty@gmail.com"
            ).first()
            if existing_faculty:
                print(f"  Faculty: {existing_faculty.email} (ID: {existing_faculty.id})")
            existing_room = db.query(Room).filter(
                Room.name == "Room 301"
            ).first()
            if existing_room:
                print(f"  Room: {existing_room.name} in {existing_room.building} (ID: {existing_room.id})")
            schedule_count = db.query(Schedule).filter(
                Schedule.subject_code == "CPE 301"
            ).count()
            print(f"  Schedules: {schedule_count} found for CPE 301")
            enrollment_count = db.query(Enrollment).filter(
                Enrollment.student_id == existing_student.id
            ).count()
            print(f"  Enrollments: {enrollment_count} for student")
            print("\nNo changes made.")
            return

        # ------------------------------------------------------------------
        # 1. Create Student User
        # ------------------------------------------------------------------
        print("\n[1/5] Creating student user...")
        student = User(
            email="cjjutbaofficial@gmail.com",
            password_hash=hash_password("password123"),
            role=UserRole.STUDENT,
            first_name="Christian Jerald",
            last_name="Jutba",
            student_id="21-A-02177",
            phone="09764556948",
            is_active=True,
        )
        db.add(student)
        db.flush()  # Obtain generated UUID without committing
        print(f"  Created: {student.first_name} {student.last_name}")
        print(f"  Email:   {student.email}")
        print(f"  Student ID: {student.student_id}")
        print(f"  DB ID:   {student.id}")

        # ------------------------------------------------------------------
        # 2. Create Faculty User
        # ------------------------------------------------------------------
        print("\n[2/5] Creating faculty user...")
        faculty = User(
            email="faculty@gmail.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY,
            first_name="Faculty",
            last_name="User",
            phone="09000000000",
            is_active=True,
        )
        db.add(faculty)
        db.flush()
        print(f"  Created: {faculty.first_name} {faculty.last_name}")
        print(f"  Email:   {faculty.email}")
        print(f"  DB ID:   {faculty.id}")

        # ------------------------------------------------------------------
        # 3. Create Room
        # ------------------------------------------------------------------
        print("\n[3/5] Creating room...")
        room = Room(
            name="Room 301",
            building="Engineering Building",
            capacity=40,
            camera_endpoint="http://192.168.1.100:8000",
            is_active=True,
        )
        db.add(room)
        db.flush()
        print(f"  Created: {room.name} in {room.building}")
        print(f"  Capacity: {room.capacity}")
        print(f"  Camera:  {room.camera_endpoint}")
        print(f"  DB ID:   {room.id}")

        # ------------------------------------------------------------------
        # 4. Create Schedules (Monday through Friday)
        # ------------------------------------------------------------------
        print("\n[4/5] Creating schedules (Mon-Fri)...")
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        schedules = []

        for day_idx, day_name in enumerate(day_names):
            schedule = Schedule(
                subject_code="CPE 301",
                subject_name="Microprocessors and Microcontrollers",
                faculty_id=faculty.id,
                room_id=room.id,
                day_of_week=day_idx,
                start_time=time(7, 0),
                end_time=time(22, 0),
                semester="2nd",
                academic_year="2025-2026",
                is_active=True,
            )
            db.add(schedule)
            db.flush()
            schedules.append(schedule)
            print(f"  Created: CPE 301 on {day_name} 07:00-22:00 (ID: {schedule.id})")

        # ------------------------------------------------------------------
        # 5. Create Enrollments (student in all 5 schedules)
        # ------------------------------------------------------------------
        print("\n[5/5] Enrolling student in all schedules...")
        for i, schedule in enumerate(schedules):
            enrollment = Enrollment(
                student_id=student.id,
                schedule_id=schedule.id,
            )
            db.add(enrollment)
            db.flush()
            print(f"  Enrolled in {day_names[i]} schedule (ID: {enrollment.id})")

        # ------------------------------------------------------------------
        # Commit the entire transaction
        # ------------------------------------------------------------------
        db.commit()
        logger.info("Seed data committed successfully")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("SEED DATA COMPLETE")
        print("=" * 60)
        print(f"\nStudent Login:")
        print(f"  Email:      cjjutbaofficial@gmail.com")
        print(f"  Student ID: 21-A-02177")
        print(f"  Password:   password123")
        print(f"\nFaculty Login:")
        print(f"  Email:      faculty@gmail.com")
        print(f"  Password:   password123")
        print(f"\nRoom: {room.name} ({room.building})")
        print(f"Schedule: CPE 301 - Mon-Fri 07:00-22:00")
        print(f"Student enrolled in {len(schedules)} schedule(s)")

    except Exception as e:
        db.rollback()
        logger.error(f"Seed failed: {e}")
        print(f"\nERROR: Seed failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
