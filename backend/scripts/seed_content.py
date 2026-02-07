"""
Seed Content Data for IAMS Backend

Creates realistic attendance records, presence logs, early leave events,
and notifications for the existing student and faculty users.

Run from backend directory:
    python -m scripts.seed_content

Prerequisites: Run seed_data first (python -m scripts.seed_data)
This script is idempotent -- it checks before inserting.
"""

import sys
import uuid
import random
from pathlib import Path
from datetime import date, datetime, time, timedelta

# Add backend to path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import (
    User, Schedule, Enrollment, AttendanceRecord, AttendanceStatus,
    PresenceLog, EarlyLeaveEvent, Notification,
)
from app.config import logger


def seed_content():
    """
    Seed realistic content data for demo/testing.

    Creates:
      - 10 days of attendance records (past 2 weeks, Mon-Fri)
      - Presence logs for each attendance record (scan every 60s)
      - Early leave events (2 events)
      - Notifications for both student and faculty
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("IAMS - Seeding Content Data")
        print("=" * 60)

        # ------------------------------------------------------------------
        # Find existing seed data
        # ------------------------------------------------------------------
        student = db.query(User).filter(User.student_id == "21-A-02177").first()
        faculty = db.query(User).filter(User.email == "faculty@gmail.com").first()

        if not student or not faculty:
            print("\nERROR: Base seed data not found. Run 'python -m scripts.seed_data' first.")
            return

        print(f"\nStudent: {student.first_name} {student.last_name} ({student.id})")
        print(f"Faculty: {faculty.first_name} {faculty.last_name} ({faculty.id})")

        # Get all schedules (Mon-Fri, day_of_week 0-4)
        schedules = (
            db.query(Schedule)
            .filter(Schedule.faculty_id == faculty.id, Schedule.subject_code == "CPE 301")
            .order_by(Schedule.day_of_week)
            .all()
        )

        if not schedules:
            print("\nERROR: No schedules found. Run 'python -m scripts.seed_data' first.")
            return

        schedule_map = {s.day_of_week: s for s in schedules}
        print(f"Schedules: {len(schedules)} found (Mon-Fri)")

        # ------------------------------------------------------------------
        # Idempotency check
        # ------------------------------------------------------------------
        existing_records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.student_id == student.id)
            .count()
        )

        if existing_records > 0:
            print(f"\nContent data already exists ({existing_records} attendance records). Skipping...")
            print("To re-seed, delete attendance_records for this student first.")
            return

        # ------------------------------------------------------------------
        # Generate weekdays for the past 2 weeks
        # ------------------------------------------------------------------
        today = date.today()  # Saturday Feb 7, 2026
        weekdays = []
        check_date = today - timedelta(days=1)  # Start from yesterday

        while len(weekdays) < 10:
            if check_date.weekday() < 5:  # Mon=0 .. Fri=4
                weekdays.append(check_date)
            check_date -= timedelta(days=1)

        weekdays.reverse()  # Oldest first
        print(f"\nGenerating data for {len(weekdays)} weekdays:")
        print(f"  From: {weekdays[0]} to {weekdays[-1]}")

        # ------------------------------------------------------------------
        # Attendance pattern: realistic mix of statuses
        # ------------------------------------------------------------------
        # Pattern for 10 days (index 0 = oldest):
        # Days 0-9: present, late, present, present, absent,
        #           present, present, early_leave, late, present
        status_pattern = [
            AttendanceStatus.PRESENT,
            AttendanceStatus.LATE,
            AttendanceStatus.PRESENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.ABSENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.EARLY_LEAVE,
            AttendanceStatus.LATE,
            AttendanceStatus.PRESENT,
        ]

        # Presence score pattern (0-100)
        score_pattern = [95.0, 85.0, 100.0, 90.0, 0.0, 92.0, 88.0, 45.0, 80.0, 97.0]

        all_attendance = []
        all_presence_logs = []
        all_early_leaves = []

        # ------------------------------------------------------------------
        # 1. Create Attendance Records + Presence Logs
        # ------------------------------------------------------------------
        print("\n[1/3] Creating attendance records and presence logs...")

        for i, day in enumerate(weekdays):
            dow = day.weekday()  # Python weekday: Mon=0..Fri=4
            schedule = schedule_map.get(dow)

            if not schedule:
                continue

            status = status_pattern[i]
            score = score_pattern[i]

            # Calculate check-in time based on status
            class_start = datetime.combine(day, time(7, 0))

            if status == AttendanceStatus.PRESENT:
                check_in = class_start - timedelta(minutes=random.randint(1, 10))
                check_out = datetime.combine(day, time(21, 50 + random.randint(0, 9)))
                total_scans = 15
                scans_present = int(total_scans * score / 100)
            elif status == AttendanceStatus.LATE:
                check_in = class_start + timedelta(minutes=random.randint(16, 30))
                check_out = datetime.combine(day, time(21, 50 + random.randint(0, 9)))
                total_scans = 15
                scans_present = int(total_scans * score / 100)
            elif status == AttendanceStatus.ABSENT:
                check_in = None
                check_out = None
                total_scans = 15
                scans_present = 0
            elif status == AttendanceStatus.EARLY_LEAVE:
                check_in = class_start - timedelta(minutes=random.randint(1, 5))
                check_out = datetime.combine(day, time(14, 30))
                total_scans = 15
                scans_present = int(total_scans * score / 100)
            else:
                check_in = class_start
                check_out = datetime.combine(day, time(22, 0))
                total_scans = 15
                scans_present = int(total_scans * score / 100)

            record = AttendanceRecord(
                student_id=student.id,
                schedule_id=schedule.id,
                date=day,
                status=status,
                check_in_time=check_in,
                check_out_time=check_out,
                presence_score=score,
                total_scans=total_scans,
                scans_present=scans_present,
                remarks=None,
            )
            db.add(record)
            db.flush()
            all_attendance.append(record)

            status_label = status.value.upper()
            print(f"  {day} ({['Mon','Tue','Wed','Thu','Fri'][dow]}) - {status_label} ({score}%)")

            # Create presence logs for this record
            scan_interval = timedelta(minutes=60)
            scan_start = datetime.combine(day, time(7, 0))

            for scan_num in range(1, total_scans + 1):
                scan_time = scan_start + scan_interval * (scan_num - 1)

                if status == AttendanceStatus.ABSENT:
                    detected = False
                    confidence = None
                elif status == AttendanceStatus.EARLY_LEAVE and scan_num > 7:
                    detected = False
                    confidence = None
                elif status == AttendanceStatus.LATE and scan_num == 1:
                    detected = False
                    confidence = None
                else:
                    # Randomly miss some scans based on score
                    detected = random.random() < (score / 100.0)
                    confidence = round(random.uniform(0.75, 0.98), 3) if detected else None

                log = PresenceLog(
                    attendance_id=record.id,
                    scan_number=scan_num,
                    scan_time=scan_time,
                    detected=detected,
                    confidence=confidence,
                )
                db.add(log)
                all_presence_logs.append(log)

        print(f"\n  Total: {len(all_attendance)} attendance records, {len(all_presence_logs)} presence logs")

        # ------------------------------------------------------------------
        # 2. Create Early Leave Events
        # ------------------------------------------------------------------
        print("\n[2/3] Creating early leave events...")

        # Find the early_leave attendance record (index 7)
        early_leave_records = [r for r in all_attendance if r.status == AttendanceStatus.EARLY_LEAVE]

        for record in early_leave_records:
            event = EarlyLeaveEvent(
                attendance_id=record.id,
                detected_at=record.check_out_time + timedelta(minutes=3),
                last_seen_at=record.check_out_time,
                consecutive_misses=3,
                notified=True,
                notified_at=record.check_out_time + timedelta(minutes=4),
            )
            db.add(event)
            db.flush()
            all_early_leaves.append(event)
            print(f"  Early leave on {record.date}: 3 consecutive misses after {record.check_out_time.strftime('%H:%M')}")

        # Also create a "borderline" early leave from a present day (simulated)
        # Use the most recent present record
        recent_present = [r for r in all_attendance if r.status == AttendanceStatus.PRESENT]
        if len(recent_present) >= 2:
            borderline_record = recent_present[-2]
            borderline_event = EarlyLeaveEvent(
                attendance_id=borderline_record.id,
                detected_at=datetime.combine(borderline_record.date, time(18, 30)),
                last_seen_at=datetime.combine(borderline_record.date, time(18, 0)),
                consecutive_misses=3,
                notified=True,
                notified_at=datetime.combine(borderline_record.date, time(18, 32)),
            )
            db.add(borderline_event)
            db.flush()
            all_early_leaves.append(borderline_event)
            print(f"  Borderline early leave on {borderline_record.date}: left at 18:00")

        print(f"  Total: {len(all_early_leaves)} early leave events")

        # ------------------------------------------------------------------
        # 3. Create Notifications
        # ------------------------------------------------------------------
        print("\n[3/3] Creating notifications...")

        notifications = []

        # Student notifications
        student_notifs = [
            {
                "user_id": student.id,
                "title": "Attendance Recorded",
                "message": "Your attendance for CPE 301 - Microprocessors and Microcontrollers has been recorded as Present.",
                "type": "attendance",
                "read": True,
                "read_at": datetime(2026, 2, 6, 8, 30),
                "reference_type": "attendance",
                "created_at": datetime(2026, 2, 6, 7, 5),
            },
            {
                "user_id": student.id,
                "title": "Late Arrival Noted",
                "message": "You were marked Late for CPE 301 on Feb 3. You checked in at 07:22, 22 minutes after class started.",
                "type": "attendance",
                "read": True,
                "read_at": datetime(2026, 2, 3, 12, 0),
                "reference_type": "attendance",
                "created_at": datetime(2026, 2, 3, 7, 25),
            },
            {
                "user_id": student.id,
                "title": "Absence Recorded",
                "message": "You were marked Absent for CPE 301 on Jan 31. Please contact your instructor if this is incorrect.",
                "type": "alert",
                "read": False,
                "read_at": None,
                "reference_type": "attendance",
                "created_at": datetime(2026, 1, 31, 22, 5),
            },
            {
                "user_id": student.id,
                "title": "Early Leave Detected",
                "message": "You left CPE 301 early on Feb 5. Last detected at 14:30. Your presence score was 45%.",
                "type": "alert",
                "read": False,
                "read_at": None,
                "reference_type": "early_leave",
                "created_at": datetime(2026, 2, 5, 14, 35),
            },
            {
                "user_id": student.id,
                "title": "Weekly Attendance Summary",
                "message": "Your attendance rate this week: 80%. You attended 4 out of 5 classes. Keep it up!",
                "type": "system",
                "read": False,
                "read_at": None,
                "reference_type": None,
                "created_at": datetime(2026, 2, 7, 8, 0),
            },
            {
                "user_id": student.id,
                "title": "Schedule Reminder",
                "message": "Your CPE 301 class starts in 30 minutes at Room 301, Engineering Building.",
                "type": "system",
                "read": True,
                "read_at": datetime(2026, 2, 6, 6, 45),
                "reference_type": "schedule",
                "created_at": datetime(2026, 2, 6, 6, 30),
            },
        ]

        # Faculty notifications
        faculty_notifs = [
            {
                "user_id": faculty.id,
                "title": "Early Leave Alert",
                "message": "Christian Jerald Jutba left CPE 301 early on Feb 5. Last seen at 14:30 (3 consecutive misses).",
                "type": "alert",
                "read": False,
                "read_at": None,
                "reference_type": "early_leave",
                "created_at": datetime(2026, 2, 5, 14, 35),
            },
            {
                "user_id": faculty.id,
                "title": "Early Leave Alert",
                "message": "Christian Jerald Jutba left CPE 301 early on Feb 4. Last seen at 18:00 (3 consecutive misses).",
                "type": "alert",
                "read": True,
                "read_at": datetime(2026, 2, 4, 19, 0),
                "reference_type": "early_leave",
                "created_at": datetime(2026, 2, 4, 18, 32),
            },
            {
                "user_id": faculty.id,
                "title": "Attendance Report Ready",
                "message": "The weekly attendance report for CPE 301 (Jan 27 - Jan 31) is ready for review.",
                "type": "system",
                "read": True,
                "read_at": datetime(2026, 2, 1, 10, 0),
                "reference_type": None,
                "created_at": datetime(2026, 2, 1, 8, 0),
            },
            {
                "user_id": faculty.id,
                "title": "Student Absence Alert",
                "message": "Christian Jerald Jutba was absent from CPE 301 on Jan 31.",
                "type": "alert",
                "read": True,
                "read_at": datetime(2026, 1, 31, 23, 0),
                "reference_type": "attendance",
                "created_at": datetime(2026, 1, 31, 22, 5),
            },
            {
                "user_id": faculty.id,
                "title": "Weekly Summary",
                "message": "CPE 301 weekly stats: 1 student enrolled. Attendance rate: 80%. 1 early leave, 1 absence this week.",
                "type": "system",
                "read": False,
                "read_at": None,
                "reference_type": None,
                "created_at": datetime(2026, 2, 7, 8, 0),
            },
        ]

        for notif_data in student_notifs + faculty_notifs:
            notif = Notification(**notif_data)
            db.add(notif)
            notifications.append(notif)

        db.flush()
        print(f"  Student notifications: {len(student_notifs)}")
        print(f"  Faculty notifications: {len(faculty_notifs)}")
        print(f"  Total: {len(notifications)} notifications")

        # ------------------------------------------------------------------
        # Commit everything
        # ------------------------------------------------------------------
        db.commit()
        logger.info("Content seed data committed successfully")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("CONTENT SEED COMPLETE")
        print("=" * 60)

        # Attendance summary
        status_counts = {}
        for r in all_attendance:
            s = r.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        print(f"\nAttendance Records: {len(all_attendance)}")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")

        avg_score = sum(r.presence_score for r in all_attendance) / len(all_attendance)
        print(f"  Average presence score: {avg_score:.1f}%")

        print(f"\nPresence Logs: {len(all_presence_logs)}")
        print(f"Early Leave Events: {len(all_early_leaves)}")
        print(f"Notifications: {len(notifications)} ({len(student_notifs)} student, {len(faculty_notifs)} faculty)")

    except Exception as e:
        db.rollback()
        logger.error(f"Content seed failed: {e}")
        print(f"\nERROR: Content seed failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_content()
