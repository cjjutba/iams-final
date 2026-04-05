"""
Notification Jobs — APScheduler background tasks for digest, attendance
monitoring, anomaly detection, and notification cleanup.

All functions follow the short-lived DB session pattern used in main.py:
open a session, do work in try/finally, always close.  Failures are logged
but never propagated so the scheduler stays healthy.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


# =====================================================================
# 1. Daily Digest
# =====================================================================


async def run_daily_digest() -> None:
    """Send daily attendance summary to users who enabled daily_digest.

    Faculty receive stats for all their classes; students receive their
    own attendance records for the day.
    """
    from app.models.notification_preference import NotificationPreference
    from app.models.user import User, UserRole
    from app.services.notification_service import notify as _notify

    db = SessionLocal()
    try:
        today = date.today()
        date_str = today.strftime("%B %d, %Y")

        # Users with daily_digest enabled
        prefs = db.query(NotificationPreference).filter(NotificationPreference.daily_digest.is_(True)).all()

        if not prefs:
            logger.debug("[daily_digest] No users with daily_digest enabled")
            return

        notified = 0
        for pref in prefs:
            user_id = str(pref.user_id)
            user = db.query(User).filter(User.id == pref.user_id).first()
            if not user:
                continue

            try:
                if user.role == UserRole.FACULTY:
                    rows_html = _build_faculty_daily_html(db, user_id, today)
                else:
                    rows_html = _build_student_daily_html(db, user_id, today)

                if not rows_html:
                    continue

                await _notify(
                    db,
                    user_id,
                    "Daily Attendance Summary",
                    f"Your attendance summary for {date_str}.",
                    "daily_digest",
                    preference_key="daily_digest",
                    toast_type="info",
                    send_email=True,
                    email_template="daily_digest",
                    email_context={
                        "date": date_str,
                        "rows_html": rows_html,
                    },
                )
                notified += 1
            except Exception:
                logger.warning(
                    "[daily_digest] Failed for user %s",
                    user_id,
                    exc_info=True,
                )

        logger.info("[daily_digest] Sent %d daily digests", notified)

    except Exception:
        logger.exception("[daily_digest] Job failed")
    finally:
        db.close()


def _build_faculty_daily_html(db, faculty_id: str, day: date) -> str | None:
    """Build HTML summary rows for a faculty member's classes on a given day."""
    import uuid

    from app.models.attendance_record import AttendanceRecord, AttendanceStatus
    from app.models.schedule import Schedule

    schedules = db.query(Schedule).filter(Schedule.faculty_id == uuid.UUID(faculty_id), Schedule.is_active).all()
    if not schedules:
        return None

    rows = []
    for sched in schedules:
        records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.schedule_id == sched.id,
                AttendanceRecord.date == day,
            )
            .all()
        )
        if not records:
            continue

        total = len(records)
        present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
        late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        early_leave = sum(1 for r in records if r.status == AttendanceStatus.EARLY_LEAVE)

        rows.append(
            f"<tr><td>{sched.subject_code}</td>"
            f"<td>{present}/{total}</td>"
            f"<td>{late}</td><td>{absent}</td><td>{early_leave}</td></tr>"
        )

    if not rows:
        return None

    return (
        "<table style='width:100%;border-collapse:collapse'>"
        "<tr><th style='text-align:left'>Subject</th>"
        "<th>Present</th><th>Late</th><th>Absent</th><th>Early Leave</th></tr>" + "".join(rows) + "</table>"
    )


def _build_student_daily_html(db, student_id: str, day: date) -> str | None:
    """Build HTML summary rows for a student's attendance on a given day."""
    import uuid

    from app.models.attendance_record import AttendanceRecord
    from app.models.schedule import Schedule

    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.student_id == uuid.UUID(student_id),
            AttendanceRecord.date == day,
        )
        .all()
    )
    if not records:
        return None

    rows = []
    for rec in records:
        sched = db.query(Schedule).filter(Schedule.id == rec.schedule_id).first()
        subject = sched.subject_code if sched else "Unknown"
        check_in = rec.check_in_time.strftime("%I:%M %p") if rec.check_in_time else "N/A"
        rows.append(f"<tr><td>{subject}</td><td>{rec.status.value}</td><td>{check_in}</td></tr>")

    return (
        "<table style='width:100%;border-collapse:collapse'>"
        "<tr><th style='text-align:left'>Subject</th>"
        "<th>Status</th><th>Check-in</th></tr>" + "".join(rows) + "</table>"
    )


# =====================================================================
# 2. Weekly Digest
# =====================================================================


async def run_weekly_digest() -> None:
    """Send weekly attendance summary (Mon-Sun) to users with weekly_digest enabled."""
    from app.models.notification_preference import NotificationPreference
    from app.models.user import User, UserRole
    from app.services.notification_service import notify as _notify

    db = SessionLocal()
    try:
        today = date.today()
        # Compute Monday-Sunday range for the current week
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        week_label = f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"

        prefs = db.query(NotificationPreference).filter(NotificationPreference.weekly_digest.is_(True)).all()

        if not prefs:
            logger.debug("[weekly_digest] No users with weekly_digest enabled")
            return

        notified = 0
        for pref in prefs:
            user_id = str(pref.user_id)
            user = db.query(User).filter(User.id == pref.user_id).first()
            if not user:
                continue

            try:
                if user.role == UserRole.FACULTY:
                    rows_html = _build_faculty_weekly_html(db, user_id, monday, sunday)
                else:
                    rows_html = _build_student_weekly_html(db, user_id, monday, sunday)

                if not rows_html:
                    continue

                await _notify(
                    db,
                    user_id,
                    "Weekly Attendance Summary",
                    f"Your attendance summary for {week_label}.",
                    "weekly_digest",
                    preference_key="weekly_digest",
                    toast_type="info",
                    send_email=True,
                    email_template="weekly_digest",
                    email_context={
                        "week_label": week_label,
                        "rows_html": rows_html,
                    },
                )
                notified += 1
            except Exception:
                logger.warning(
                    "[weekly_digest] Failed for user %s",
                    user_id,
                    exc_info=True,
                )

        logger.info("[weekly_digest] Sent %d weekly digests", notified)

    except Exception:
        logger.exception("[weekly_digest] Job failed")
    finally:
        db.close()


def _build_faculty_weekly_html(
    db,
    faculty_id: str,
    start: date,
    end: date,
) -> str | None:
    """Build HTML weekly summary for a faculty member."""
    import uuid

    from app.models.attendance_record import AttendanceRecord, AttendanceStatus
    from app.models.schedule import Schedule

    schedules = db.query(Schedule).filter(Schedule.faculty_id == uuid.UUID(faculty_id), Schedule.is_active).all()
    if not schedules:
        return None

    rows = []
    for sched in schedules:
        records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.schedule_id == sched.id,
                AttendanceRecord.date >= start,
                AttendanceRecord.date <= end,
            )
            .all()
        )
        if not records:
            continue

        total = len(records)
        present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
        late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        early_leave = sum(1 for r in records if r.status == AttendanceStatus.EARLY_LEAVE)
        rate = round((present / total) * 100, 1) if total > 0 else 0.0

        rows.append(
            f"<tr><td>{sched.subject_code}</td>"
            f"<td>{rate}%</td>"
            f"<td>{present}</td><td>{late}</td><td>{absent}</td><td>{early_leave}</td></tr>"
        )

    if not rows:
        return None

    return (
        "<table style='width:100%;border-collapse:collapse'>"
        "<tr><th style='text-align:left'>Subject</th>"
        "<th>Rate</th><th>Present</th><th>Late</th><th>Absent</th><th>Early Leave</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _build_student_weekly_html(
    db,
    student_id: str,
    start: date,
    end: date,
) -> str | None:
    """Build HTML weekly summary for a student."""
    import uuid

    from app.models.attendance_record import AttendanceRecord, AttendanceStatus
    from app.models.schedule import Schedule

    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.student_id == uuid.UUID(student_id),
            AttendanceRecord.date >= start,
            AttendanceRecord.date <= end,
        )
        .all()
    )
    if not records:
        return None

    # Group by schedule
    by_schedule: dict[str, list] = {}
    for rec in records:
        sid = str(rec.schedule_id)
        by_schedule.setdefault(sid, []).append(rec)

    rows = []
    for sid, recs in by_schedule.items():
        sched = db.query(Schedule).filter(Schedule.id == uuid.UUID(sid)).first()
        subject = sched.subject_code if sched else "Unknown"
        total = len(recs)
        present = sum(1 for r in recs if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
        rate = round((present / total) * 100, 1) if total > 0 else 0.0

        rows.append(f"<tr><td>{subject}</td><td>{rate}%</td><td>{present}/{total}</td></tr>")

    return (
        "<table style='width:100%;border-collapse:collapse'>"
        "<tr><th style='text-align:left'>Subject</th>"
        "<th>Rate</th><th>Present/Total</th></tr>" + "".join(rows) + "</table>"
    )


# =====================================================================
# 3. Low Attendance Check
# =====================================================================


async def run_low_attendance_check() -> None:
    """Check enrolled students for low attendance over a rolling window.

    Compares each student's attendance rate against their personal threshold
    (or the default 75%). Deduplicates by skipping students who received a
    low_attendance_warning within LOW_ATTENDANCE_RENOTIFY_DAYS.
    """

    from app.models.attendance_record import AttendanceRecord, AttendanceStatus
    from app.models.enrollment import Enrollment
    from app.models.notification import Notification
    from app.models.notification_preference import NotificationPreference
    from app.models.schedule import Schedule
    from app.models.user import User
    from app.services.notification_service import notify as _notify

    db = SessionLocal()
    try:
        today = date.today()
        window_start = today - timedelta(days=settings.LOW_ATTENDANCE_CHECK_WINDOW_DAYS)
        renotify_cutoff = datetime.now(UTC) - timedelta(days=settings.LOW_ATTENDANCE_RENOTIFY_DAYS)

        # Active schedules with enrollments
        schedules = db.query(Schedule).filter(Schedule.is_active).all()

        warned = 0
        for sched in schedules:
            enrollments = db.query(Enrollment).filter(Enrollment.schedule_id == sched.id).all()

            for enrollment in enrollments:
                student_id = str(enrollment.student_id)

                try:
                    # Compute attendance rate in the rolling window
                    records = (
                        db.query(AttendanceRecord)
                        .filter(
                            AttendanceRecord.student_id == enrollment.student_id,
                            AttendanceRecord.schedule_id == sched.id,
                            AttendanceRecord.date >= window_start,
                            AttendanceRecord.date <= today,
                        )
                        .all()
                    )

                    if not records:
                        continue

                    total = len(records)
                    present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
                    rate = (present / total) * 100.0

                    # Get user's threshold (default 75%)
                    pref = (
                        db.query(NotificationPreference)
                        .filter(NotificationPreference.user_id == enrollment.student_id)
                        .first()
                    )
                    threshold = pref.low_attendance_threshold if pref else 75.0

                    if rate >= threshold:
                        continue

                    # Deduplicate: skip if warned recently
                    recent_warning = (
                        db.query(Notification)
                        .filter(
                            Notification.user_id == enrollment.student_id,
                            Notification.type == "low_attendance_warning",
                            Notification.created_at >= renotify_cutoff,
                        )
                        .first()
                    )
                    if recent_warning:
                        continue

                    # Notify student
                    student = db.query(User).filter(User.id == enrollment.student_id).first()
                    student_name = student.first_name if student else "Student"

                    await _notify(
                        db,
                        student_id,
                        "Low Attendance Warning",
                        f"Your attendance for {sched.subject_code} is at {rate:.0f}%, "
                        f"below the {threshold:.0f}% threshold.",
                        "low_attendance_warning",
                        preference_key="low_attendance_warning",
                        toast_type="warning",
                        send_email=True,
                        email_template="low_attendance",
                        email_context={
                            "student_name": student_name,
                            "subject_code": sched.subject_code,
                            "presence_score": f"{rate:.0f}",
                            "threshold": f"{threshold:.0f}",
                        },
                    )

                    # Notify faculty
                    faculty_id = str(sched.faculty_id)
                    await _notify(
                        db,
                        faculty_id,
                        "Student Low Attendance",
                        f"{student_name} has {rate:.0f}% attendance in {sched.subject_code}.",
                        "low_attendance_warning",
                        preference_key="low_attendance_warning",
                        toast_type="warning",
                    )

                    warned += 1

                except Exception:
                    logger.warning(
                        "[low_attendance] Failed for student %s in schedule %s",
                        student_id,
                        str(sched.id)[:8],
                        exc_info=True,
                    )

        logger.info("[low_attendance] Warned %d student-schedule pairs", warned)

    except Exception:
        logger.exception("[low_attendance] Job failed")
    finally:
        db.close()


# =====================================================================
# 4. Anomaly Detection
# =====================================================================


async def run_anomaly_detection() -> None:
    """Detect attendance anomalies: early-leave patterns and sudden drops.

    - EARLY_LEAVE_PATTERN: 3+ early leave events in last 7 days for same student+schedule
    - SUDDEN_DROP: >= 80% in prior 2 weeks, < 50% this week
    """

    from app.models.attendance_anomaly import AnomalyType, AttendanceAnomaly
    from app.models.attendance_record import AttendanceRecord, AttendanceStatus
    from app.models.early_leave_event import EarlyLeaveEvent
    from app.models.enrollment import Enrollment
    from app.models.schedule import Schedule
    from app.models.user import User
    from app.services.notification_service import notify as _notify

    db = SessionLocal()
    try:
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)
        this_week_start = today - timedelta(days=today.weekday())

        schedules = db.query(Schedule).filter(Schedule.is_active).all()
        anomalies_created = 0

        for sched in schedules:
            enrollments = db.query(Enrollment).filter(Enrollment.schedule_id == sched.id).all()
            faculty_id = str(sched.faculty_id)

            for enrollment in enrollments:
                student_id = str(enrollment.student_id)
                student_uuid = enrollment.student_id

                try:
                    # --- EARLY_LEAVE_PATTERN ---
                    el_count = (
                        db.query(func.count(EarlyLeaveEvent.id))
                        .join(
                            AttendanceRecord,
                            EarlyLeaveEvent.attendance_id == AttendanceRecord.id,
                        )
                        .filter(
                            AttendanceRecord.student_id == student_uuid,
                            AttendanceRecord.schedule_id == sched.id,
                            EarlyLeaveEvent.detected_at >= datetime.combine(seven_days_ago, datetime.min.time()),
                        )
                        .scalar()
                    ) or 0

                    if el_count >= 3:
                        # Check for existing unresolved anomaly of same type
                        existing = (
                            db.query(AttendanceAnomaly)
                            .filter(
                                AttendanceAnomaly.student_id == student_uuid,
                                AttendanceAnomaly.schedule_id == sched.id,
                                AttendanceAnomaly.anomaly_type == AnomalyType.EARLY_LEAVE_PATTERN,
                                AttendanceAnomaly.resolved.is_(False),
                            )
                            .first()
                        )
                        if not existing:
                            student = db.query(User).filter(User.id == student_uuid).first()
                            student_name = student.first_name if student else "Student"

                            anomaly = AttendanceAnomaly(
                                student_id=student_uuid,
                                schedule_id=sched.id,
                                anomaly_type=AnomalyType.EARLY_LEAVE_PATTERN,
                                severity="medium",
                                description=(
                                    f"{student_name} has {el_count} early leaves in "
                                    f"{sched.subject_code} over the past 7 days."
                                ),
                                confidence=min(1.0, el_count / 5.0),
                            )
                            db.add(anomaly)
                            db.commit()
                            anomalies_created += 1

                            await _notify(
                                db,
                                faculty_id,
                                "Attendance Anomaly",
                                f"{student_name} has {el_count} early leaves in {sched.subject_code} this week.",
                                "anomaly_alert",
                                preference_key="anomaly_alerts",
                                toast_type="warning",
                            )

                    # --- SUDDEN_DROP ---
                    prior_records = (
                        db.query(AttendanceRecord)
                        .filter(
                            AttendanceRecord.student_id == student_uuid,
                            AttendanceRecord.schedule_id == sched.id,
                            AttendanceRecord.date >= two_weeks_ago,
                            AttendanceRecord.date < this_week_start,
                        )
                        .all()
                    )
                    this_week_records = (
                        db.query(AttendanceRecord)
                        .filter(
                            AttendanceRecord.student_id == student_uuid,
                            AttendanceRecord.schedule_id == sched.id,
                            AttendanceRecord.date >= this_week_start,
                            AttendanceRecord.date <= today,
                        )
                        .all()
                    )

                    if prior_records and this_week_records:
                        prior_total = len(prior_records)
                        prior_present = sum(
                            1 for r in prior_records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
                        )
                        prior_rate = (prior_present / prior_total) * 100.0

                        this_total = len(this_week_records)
                        this_present = sum(
                            1
                            for r in this_week_records
                            if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
                        )
                        this_rate = (this_present / this_total) * 100.0

                        if prior_rate >= 80.0 and this_rate < 50.0:
                            existing = (
                                db.query(AttendanceAnomaly)
                                .filter(
                                    AttendanceAnomaly.student_id == student_uuid,
                                    AttendanceAnomaly.schedule_id == sched.id,
                                    AttendanceAnomaly.anomaly_type == AnomalyType.SUDDEN_DROP,
                                    AttendanceAnomaly.resolved.is_(False),
                                )
                                .first()
                            )
                            if not existing:
                                student = db.query(User).filter(User.id == student_uuid).first()
                                student_name = student.first_name if student else "Student"

                                anomaly = AttendanceAnomaly(
                                    student_id=student_uuid,
                                    schedule_id=sched.id,
                                    anomaly_type=AnomalyType.SUDDEN_DROP,
                                    severity="high",
                                    description=(
                                        f"{student_name}'s attendance in {sched.subject_code} "
                                        f"dropped from {prior_rate:.0f}% to {this_rate:.0f}%."
                                    ),
                                    confidence=0.9,
                                )
                                db.add(anomaly)
                                db.commit()
                                anomalies_created += 1

                                await _notify(
                                    db,
                                    faculty_id,
                                    "Sudden Attendance Drop",
                                    f"{student_name}'s attendance in {sched.subject_code} "
                                    f"dropped from {prior_rate:.0f}% to {this_rate:.0f}%.",
                                    "anomaly_alert",
                                    preference_key="anomaly_alerts",
                                    toast_type="warning",
                                )

                except Exception:
                    logger.warning(
                        "[anomaly] Failed for student %s in schedule %s",
                        student_id,
                        str(sched.id)[:8],
                        exc_info=True,
                    )

        logger.info("[anomaly] Created %d anomaly records", anomalies_created)

    except Exception:
        logger.exception("[anomaly] Job failed")
    finally:
        db.close()


# =====================================================================
# 5. Notification Cleanup
# =====================================================================


async def run_notification_cleanup() -> None:
    """Delete read notifications older than NOTIFICATION_RETENTION_DAYS.

    Unread notifications are kept indefinitely so users never miss them.
    """
    from app.models.notification import Notification

    db = SessionLocal()
    try:
        cutoff = datetime.now(UTC) - timedelta(days=settings.NOTIFICATION_RETENTION_DAYS)

        count = (
            db.query(Notification)
            .filter(
                Notification.read.is_(True),
                Notification.created_at < cutoff,
            )
            .delete(synchronize_session="fetch")
        )
        db.commit()

        logger.info("[notification_cleanup] Pruned %d old read notifications", count)

    except Exception:
        logger.exception("[notification_cleanup] Job failed")
        db.rollback()
    finally:
        db.close()
