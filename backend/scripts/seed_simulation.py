"""
Simulation Seed Script for IAMS Backend

Creates realistic mid-semester data so faculty and student portals
show meaningful content (enrolled students, attendance history,
presence logs, early-leave events, notifications).

Must run AFTER seed_all (depends on faculty user, rooms, schedules,
and student_records already existing).

Run from backend directory:
    python -m scripts.seed_simulation

This script is idempotent -- skips if student users already exist.
"""

import sys
import struct
import random
from pathlib import Path
from datetime import datetime, date, time, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import (
    User, UserRole, StudentRecord, Schedule, Enrollment,
    AttendanceRecord, AttendanceStatus, PresenceLog,
    EarlyLeaveEvent, FaceRegistration, Notification,
)
from app.utils.security import hash_password
from app.config import logger
from scripts.seed_data import _sync_supabase_auth_user

# Fixed seed for reproducible "random" data
random.seed(42)

# Simulation window: 4 weeks of class history
SIM_WEEKS = 4


def _generate_status():
    """Return a random attendance status with realistic distribution."""
    r = random.random()
    if r < 0.70:
        return AttendanceStatus.PRESENT
    elif r < 0.85:
        return AttendanceStatus.LATE
    elif r < 0.95:
        return AttendanceStatus.ABSENT
    else:
        return AttendanceStatus.EARLY_LEAVE


def _class_duration_minutes(start: time, end: time) -> int:
    """Compute class duration in minutes (capped at 180 for scan count)."""
    s = start.hour * 60 + start.minute
    e = end.hour * 60 + end.minute
    return min(e - s, 180)  # Cap at 3 hours for scan counts


def seed_simulation():
    """
    Create simulation data: student users, enrollments, face registrations,
    attendance records, presence logs, early-leave events, and notifications.
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Simulation Data")
        print("=" * 60)

        # ------------------------------------------------------------------
        # 0. Idempotency check
        # ------------------------------------------------------------------
        existing_students = db.query(User).filter(
            User.role == UserRole.STUDENT
        ).count()
        if existing_students > 0:
            print(f"\nSimulation data already exists ({existing_students} student users). Skipping...")
            return

        # Verify prerequisites
        faculty = db.query(User).filter(User.email == "faculty@gmail.com").first()
        if not faculty:
            print("\nERROR: Faculty user not found. Run seed_data first.")
            return

        schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        if not schedules:
            print("\nERROR: No schedules found. Run seed_data first.")
            return

        student_records = db.query(StudentRecord).filter(
            StudentRecord.is_active == True
        ).all()
        if not student_records:
            print("\nERROR: No student records found. Run seed_reference_data first.")
            return

        # Group schedules by target_year_level
        schedules_by_year = {}
        for s in schedules:
            schedules_by_year.setdefault(s.target_year_level, []).append(s)

        # ------------------------------------------------------------------
        # 1. Create Student User Accounts
        # ------------------------------------------------------------------
        print("\n[1/7] Creating student user accounts...")
        common_hash = hash_password("password123")  # Compute once (bcrypt is slow)
        student_users = {}  # student_id -> User object

        skipped_no_email = 0
        skipped_dup_email = 0
        seen_emails = set()
        for sr in student_records:
            if not sr.email:
                skipped_no_email += 1
                continue
            email_lower = sr.email.lower()
            if email_lower in seen_emails:
                skipped_dup_email += 1
                continue
            seen_emails.add(email_lower)
            user = User(
                email=sr.email,
                password_hash=common_hash,
                role=UserRole.STUDENT,
                first_name=sr.first_name,
                last_name=sr.last_name,
                student_id=sr.student_id,
                phone=sr.contact_number,
                email_verified=True,
                is_active=True,
            )
            db.add(user)
            student_users[sr.student_id] = (user, sr.year_level)
        if skipped_no_email:
            print(f"  Skipped {skipped_no_email} students without email")
        if skipped_dup_email:
            print(f"  Skipped {skipped_dup_email} students with duplicate email")

        db.flush()  # Get UUIDs

        # Link Supabase Auth
        for sr in student_records:
            if sr.student_id not in student_users:
                continue
            user, _ = student_users[sr.student_id]
            print(f"  Created: {sr.student_id} — {sr.first_name} {sr.last_name} (ID: {user.id})")
            try:
                sb_id = _sync_supabase_auth_user(
                    email=sr.email,
                    password="password123",
                    metadata={
                        "first_name": sr.first_name,
                        "last_name": sr.last_name,
                        "role": "student",
                        "student_id": sr.student_id,
                    },
                )
                if sb_id:
                    user.supabase_user_id = sb_id
            except Exception as e:
                print(f"    Supabase Auth warning for {sr.email}: {e}")

        db.flush()
        print(f"  Total: {len(student_users)} student accounts")

        # ------------------------------------------------------------------
        # 2. Create Enrollments
        # ------------------------------------------------------------------
        print("\n[2/7] Creating enrollments...")
        enrollment_count = 0
        semester_start = date.today() - timedelta(weeks=6)
        enrolled_at = datetime.combine(semester_start, time(8, 0))

        for sid, (user, year_level) in student_users.items():
            year_schedules = schedules_by_year.get(year_level, [])
            for sched in year_schedules:
                enrollment = Enrollment(
                    student_id=user.id,
                    schedule_id=sched.id,
                    enrolled_at=enrolled_at,
                )
                db.add(enrollment)
                enrollment_count += 1

        db.flush()
        print(f"  Total: {enrollment_count} enrollments")

        # ------------------------------------------------------------------
        # 3. Create Face Registrations (dummy embeddings)
        # ------------------------------------------------------------------
        print("\n[3/7] Creating face registrations...")
        dummy_embedding = struct.pack("512f", *([0.0] * 512))

        for idx, (sid, (user, _)) in enumerate(student_users.items()):
            face_reg = FaceRegistration(
                user_id=user.id,
                embedding_id=idx,
                embedding_vector=dummy_embedding,
                registered_at=enrolled_at + timedelta(days=1),
                is_active=True,
            )
            db.add(face_reg)

        db.flush()
        print(f"  Total: {len(student_users)} face registrations")

        # ------------------------------------------------------------------
        # 4. Create Attendance Records
        # ------------------------------------------------------------------
        print("\n[4/7] Creating attendance records...")
        today = date.today()
        sim_start = today - timedelta(weeks=SIM_WEEKS)

        # Build all dates in the simulation window
        all_dates = []
        d = sim_start
        while d <= today:
            all_dates.append(d)
            d += timedelta(days=1)

        attendance_records = []  # Collect for later (presence logs, etc.)
        early_leave_records = []  # Track for early leave events
        attendance_count = 0

        for record_date in all_dates:
            dow = record_date.weekday()  # 0=Monday

            # Find schedules for this day of the week
            day_schedules = [s for s in schedules if s.day_of_week == dow]

            for sched in day_schedules:
                # Find enrolled students for this schedule's year level
                year_students = [
                    (sid, u) for sid, (u, yl) in student_users.items()
                    if yl == sched.target_year_level
                ]

                class_mins = _class_duration_minutes(sched.start_time, sched.end_time)
                total_scans = max(class_mins, 10)  # At least 10 scans
                class_start_dt = datetime.combine(record_date, sched.start_time)
                class_end_dt = datetime.combine(record_date, sched.end_time)

                for sid, user in year_students:
                    # Today's records: bias toward present (simulates active class)
                    if record_date == today:
                        status = random.choice([
                            AttendanceStatus.PRESENT,
                            AttendanceStatus.PRESENT,
                            AttendanceStatus.PRESENT,
                            AttendanceStatus.LATE,
                        ])
                    else:
                        status = _generate_status()

                    # Compute fields based on status
                    if status == AttendanceStatus.PRESENT:
                        offset_min = random.randint(-5, 5)
                        check_in = class_start_dt + timedelta(minutes=max(offset_min, 0))
                        check_out = class_end_dt - timedelta(minutes=random.randint(0, 2))
                        presence_score = round(random.uniform(85, 100), 1)
                        scans_present = round(total_scans * presence_score / 100)

                    elif status == AttendanceStatus.LATE:
                        offset_min = random.randint(6, 15)
                        check_in = class_start_dt + timedelta(minutes=offset_min)
                        check_out = class_end_dt - timedelta(minutes=random.randint(0, 2))
                        presence_score = round(random.uniform(60, 80), 1)
                        scans_present = round(total_scans * presence_score / 100)

                    elif status == AttendanceStatus.ABSENT:
                        check_in = None
                        check_out = None
                        presence_score = 0.0
                        scans_present = 0

                    else:  # EARLY_LEAVE
                        offset_min = random.randint(-3, 3)
                        check_in = class_start_dt + timedelta(minutes=max(offset_min, 0))
                        # Left somewhere between 40-70% through the class
                        leave_pct = random.uniform(0.4, 0.7)
                        check_out = class_start_dt + timedelta(minutes=int(class_mins * leave_pct))
                        presence_score = round(random.uniform(40, 65), 1)
                        scans_present = round(total_scans * presence_score / 100)

                    record = AttendanceRecord(
                        student_id=user.id,
                        schedule_id=sched.id,
                        date=record_date,
                        status=status,
                        check_in_time=check_in,
                        check_out_time=check_out,
                        presence_score=presence_score,
                        total_scans=total_scans,
                        scans_present=scans_present,
                    )
                    db.add(record)
                    attendance_records.append((record, sched))
                    attendance_count += 1

                    if status == AttendanceStatus.EARLY_LEAVE:
                        early_leave_records.append((record, sched, user))

        db.flush()  # Get attendance record IDs
        print(f"  Total: {attendance_count} attendance records")

        # ------------------------------------------------------------------
        # 5. Create Presence Logs (recent records only)
        # ------------------------------------------------------------------
        print("\n[5/7] Creating presence logs...")
        log_count = 0

        # Group attendance by student, take most recent 5 non-absent per student
        student_attendance = {}
        for rec, sched in attendance_records:
            if rec.status != AttendanceStatus.ABSENT:
                student_attendance.setdefault(rec.student_id, []).append((rec, sched))

        for student_id, records in student_attendance.items():
            # Sort by date desc, take 5 most recent
            records.sort(key=lambda x: x[0].date, reverse=True)
            recent = records[:5]

            for rec, sched in recent:
                num_logs = random.randint(12, 20)
                class_start_dt = datetime.combine(rec.date, sched.start_time)

                for i in range(num_logs):
                    scan_time = class_start_dt + timedelta(seconds=i * 60)
                    detected = random.random() < (rec.presence_score / 100.0)
                    confidence = round(random.uniform(0.85, 0.98), 4) if detected else None

                    log = PresenceLog(
                        attendance_id=rec.id,
                        scan_number=i + 1,
                        scan_time=scan_time,
                        detected=detected,
                        confidence=confidence,
                    )
                    db.add(log)
                    log_count += 1

        db.flush()
        print(f"  Total: {log_count} presence logs")

        # ------------------------------------------------------------------
        # 6. Create Early Leave Events
        # ------------------------------------------------------------------
        print("\n[6/7] Creating early leave events...")
        el_count = 0

        for rec, sched, user in early_leave_records:
            if rec.check_out_time is None:
                continue
            last_seen = rec.check_out_time
            detected_at = last_seen + timedelta(minutes=3)
            notified = random.random() < 0.8

            event = EarlyLeaveEvent(
                attendance_id=rec.id,
                detected_at=detected_at,
                last_seen_at=last_seen,
                consecutive_misses=3,
                notified=notified,
                notified_at=detected_at + timedelta(seconds=5) if notified else None,
            )
            db.add(event)
            el_count += 1

        db.flush()
        print(f"  Total: {el_count} early leave events")

        # ------------------------------------------------------------------
        # 7. Create Notifications
        # ------------------------------------------------------------------
        print("\n[7/7] Creating notifications...")
        notif_count = 0

        # Student notifications
        for sid, (user, year_level) in student_users.items():
            # Welcome notification
            db.add(Notification(
                user_id=user.id,
                title="Welcome to IAMS",
                message=(
                    f"Welcome {user.first_name}! Your account has been created "
                    "and your face has been registered successfully. "
                    "You'll receive attendance confirmations automatically."
                ),
                type="system",
                read=True,
                read_at=enrolled_at + timedelta(days=1, hours=1),
                created_at=enrolled_at + timedelta(days=1),
            ))
            notif_count += 1

            # Recent attendance confirmations (last 4 non-absent records)
            student_recs = [
                (r, s) for r, s in attendance_records
                if r.student_id == user.id and r.status != AttendanceStatus.ABSENT
            ]
            student_recs.sort(key=lambda x: x[0].date, reverse=True)

            for rec, sched in student_recs[:4]:
                status_label = rec.status.value.replace("_", " ").title()
                is_recent = (today - rec.date).days <= 2
                db.add(Notification(
                    user_id=user.id,
                    title="Attendance Recorded",
                    message=(
                        f"Your attendance for {sched.subject_code} on "
                        f"{rec.date.strftime('%b %d')} has been recorded. "
                        f"Status: {status_label}."
                    ),
                    type="attendance",
                    read=not is_recent,
                    read_at=None if is_recent else datetime.combine(
                        rec.date, time(18, 0)
                    ),
                    reference_id=str(rec.id),
                    reference_type="attendance",
                    created_at=rec.check_in_time or datetime.combine(
                        rec.date, sched.start_time
                    ),
                ))
                notif_count += 1

        # Early leave notifications for students
        for rec, sched, user in early_leave_records:
            db.add(Notification(
                user_id=user.id,
                title="Early Leave Detected",
                message=(
                    f"You were flagged for leaving {sched.subject_code} "
                    f"early on {rec.date.strftime('%b %d')}. "
                    "Please contact your instructor if this was an error."
                ),
                type="alert",
                read=False,
                reference_type="early_leave",
                created_at=rec.check_out_time + timedelta(minutes=5) if rec.check_out_time else None,
            ))
            notif_count += 1

        # Faculty notifications — daily summaries for the past week
        for record_date in all_dates[-7:]:
            dow = record_date.weekday()
            day_schedules = [s for s in schedules if s.day_of_week == dow]

            for sched in day_schedules:
                day_recs = [
                    r for r, s in attendance_records
                    if s.id == sched.id and r.date == record_date
                ]
                if not day_recs:
                    continue

                present = sum(1 for r in day_recs if r.status == AttendanceStatus.PRESENT)
                late = sum(1 for r in day_recs if r.status == AttendanceStatus.LATE)
                absent = sum(1 for r in day_recs if r.status == AttendanceStatus.ABSENT)
                total = len(day_recs)
                is_today = record_date == today

                db.add(Notification(
                    user_id=faculty.id,
                    title=f"Attendance: {sched.subject_code}",
                    message=(
                        f"{present + late}/{total} students attended {sched.subject_code} "
                        f"on {record_date.strftime('%b %d')}. "
                        f"{present} present, {late} late, {absent} absent."
                    ),
                    type="attendance",
                    read=not is_today,
                    read_at=None if is_today else datetime.combine(
                        record_date, time(22, 0)
                    ),
                    created_at=datetime.combine(record_date, sched.end_time),
                ))
                notif_count += 1

        # Faculty early-leave alerts
        for rec, sched, user in early_leave_records:
            db.add(Notification(
                user_id=faculty.id,
                title="Early Leave Alert",
                message=(
                    f"{user.first_name} {user.last_name} ({user.student_id}) "
                    f"left {sched.subject_code} early on "
                    f"{rec.date.strftime('%b %d')}."
                ),
                type="alert",
                read=(today - rec.date).days > 3,
                reference_type="early_leave",
                created_at=rec.check_out_time + timedelta(minutes=3) if rec.check_out_time else None,
            ))
            notif_count += 1

        db.flush()
        print(f"  Total: {notif_count} notifications")

        # ------------------------------------------------------------------
        # Commit
        # ------------------------------------------------------------------
        db.commit()
        logger.info("Simulation data committed successfully")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("SIMULATION SEED COMPLETE")
        print("=" * 60)
        print(f"\n  Student Users:       {len(student_users)}")
        print(f"  Enrollments:         {enrollment_count}")
        print(f"  Face Registrations:  {len(student_users)}")
        print(f"  Attendance Records:  {attendance_count}")
        print(f"  Presence Logs:       {log_count}")
        print(f"  Early Leave Events:  {el_count}")
        print(f"  Notifications:       {notif_count}")
        print(f"\nDate range: {sim_start} to {today} ({SIM_WEEKS} weeks)")
        print(f"\nStudent logins (all use password123):")
        for sr in student_records:
            print(f"  {sr.student_id}  {sr.first_name:<20} {sr.email}")

    except Exception as e:
        db.rollback()
        logger.error(f"Simulation seed failed: {e}")
        print(f"\nERROR: Simulation seed failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_simulation()
