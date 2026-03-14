"""
Digest Service

Generates daily and weekly attendance summaries for faculty and students.
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import logger
from app.models.attendance_anomaly import AttendanceAnomaly
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.early_leave_event import EarlyLeaveEvent
from app.models.notification_preference import NotificationPreference
from app.models.schedule import Schedule
from app.models.user import User, UserRole

# ---------------------------------------------------------------------------
# Pure digest builders (stateless, testable)
# ---------------------------------------------------------------------------


def build_faculty_daily_digest(
    total_classes: int,
    attendance_rates: list[float],
    anomaly_count: int,
    early_leave_count: int,
) -> dict[str, Any]:
    """
    Build a faculty daily digest summary.

    Args:
        total_classes: Number of classes taught today
        attendance_rates: Per-class attendance rates
        anomaly_count: Number of anomalies detected
        early_leave_count: Number of early leave events

    Returns:
        Dict with digest data
    """
    avg_rate = sum(attendance_rates) / len(attendance_rates) if attendance_rates else 0.0

    return {
        "digest_type": "faculty_daily",
        "date": date.today().isoformat(),
        "total_classes": total_classes,
        "average_attendance_rate": round(avg_rate, 1),
        "anomaly_count": anomaly_count,
        "early_leave_count": early_leave_count,
        "summary_text": (
            f"Today: {total_classes} classes, {avg_rate:.0f}% avg attendance"
            f"{f', {anomaly_count} anomalies' if anomaly_count else ''}"
            f"{f', {early_leave_count} early leaves' if early_leave_count else ''}"
        ),
    }


def build_student_weekly_digest(
    attendance_rate: float,
    classes_attended: int,
    classes_total: int,
    subject_breakdown: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build a student weekly digest summary.

    Args:
        attendance_rate: Overall attendance rate for the week
        classes_attended: Number of classes attended
        classes_total: Total number of classes
        subject_breakdown: Per-subject attendance data

    Returns:
        Dict with digest data
    """
    return {
        "digest_type": "student_weekly",
        "week_ending": date.today().isoformat(),
        "attendance_rate": round(attendance_rate, 1),
        "classes_attended": classes_attended,
        "classes_total": classes_total,
        "subject_breakdown": subject_breakdown,
        "summary_text": (
            f"This week: {classes_attended}/{classes_total} classes attended ({attendance_rate:.0f}% rate)"
        ),
    }


# ---------------------------------------------------------------------------
# Orchestrator (DB-aware)
# ---------------------------------------------------------------------------


class DigestService:
    """Generates and sends digest notifications."""

    def __init__(self, db: Session, notification_service=None, email_service=None):
        self.db = db
        self.notification_service = notification_service
        self.email_service = email_service

    def generate_faculty_daily_digests(self, target_date: date = None):
        """Generate daily digests for all faculty who opted in."""
        target_date = target_date or date.today()
        created = 0

        # Get faculty who want daily digests
        faculty_prefs = (
            self.db.query(NotificationPreference)
            .join(User, NotificationPreference.user_id == User.id)
            .filter(
                User.role == UserRole.FACULTY,
                NotificationPreference.daily_digest == True,  # noqa: E712
            )
            .all()
        )

        for pref in faculty_prefs:
            faculty_id = str(pref.user_id)

            # Get today's schedules for this faculty
            schedules = self.db.query(Schedule).filter(Schedule.faculty_id == pref.user_id).all()

            attendance_rates = []
            for schedule in schedules:
                records = (
                    self.db.query(AttendanceRecord)
                    .filter(
                        AttendanceRecord.schedule_id == schedule.id,
                        AttendanceRecord.date == target_date,
                    )
                    .all()
                )
                if records:
                    present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
                    attendance_rates.append((present / len(records)) * 100.0)

            # Count anomalies and early leaves
            anomaly_count = (
                self.db.query(func.count(AttendanceAnomaly.id))
                .filter(
                    AttendanceAnomaly.detected_at >= datetime.combine(target_date, datetime.min.time()),
                    AttendanceAnomaly.detected_at
                    < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                )
                .scalar()
                or 0
            )

            early_leave_count = (
                self.db.query(func.count(EarlyLeaveEvent.id))
                .filter(
                    EarlyLeaveEvent.detected_at >= datetime.combine(target_date, datetime.min.time()),
                    EarlyLeaveEvent.detected_at
                    < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                )
                .scalar()
                or 0
            )

            digest = build_faculty_daily_digest(
                total_classes=len(schedules),
                attendance_rates=attendance_rates,
                anomaly_count=anomaly_count,
                early_leave_count=early_leave_count,
            )

            # Send via notification service if available
            if self.notification_service:
                try:
                    self.notification_service.create_persisted_notification(
                        user_id=faculty_id,
                        title="Daily Attendance Summary",
                        message=digest["summary_text"],
                        notification_type="digest",
                        data=digest,
                    )
                except Exception as e:
                    logger.error(f"Failed to send daily digest to {faculty_id}: {e}")

            # Send email digest if enabled
            if self.email_service and pref.email_enabled:
                try:
                    faculty = self.db.query(User).filter(User.id == pref.user_id).first()
                    if faculty and faculty.email:
                        session_details = []
                        for schedule in schedules:
                            records = (
                                self.db.query(AttendanceRecord)
                                .filter(AttendanceRecord.schedule_id == schedule.id, AttendanceRecord.date == target_date)
                                .all()
                            )
                            if records:
                                present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
                                session_details.append({
                                    "subject_code": schedule.subject_code,
                                    "time": f"{schedule.start_time}–{schedule.end_time}" if hasattr(schedule, "start_time") else "",
                                    "rate": (present / len(records)) * 100.0,
                                    "present": present,
                                    "enrolled": len(records),
                                })
                        self.email_service.send_daily_digest_email(
                            faculty_email=faculty.email,
                            faculty_name=f"{faculty.first_name} {faculty.last_name}",
                            digest_data={
                                "date": target_date.strftime("%B %d, %Y"),
                                "total_sessions": len(schedules),
                                "avg_attendance_rate": digest["average_attendance_rate"],
                                "early_leaves": early_leave_count,
                                "anomalies": anomaly_count,
                                "session_details": session_details,
                            },
                        )
                except Exception as e:
                    logger.error(f"Failed to send daily digest email to {faculty_id}: {e}")

            created += 1

        logger.info(f"Generated {created} faculty daily digests for {target_date}")
        return created

    def generate_student_weekly_digests(self, week_ending: date = None):
        """Generate weekly digests for all students who opted in."""
        week_ending = week_ending or date.today()
        week_start = week_ending - timedelta(days=6)
        created = 0

        # Get students who want weekly digests
        student_prefs = (
            self.db.query(NotificationPreference)
            .join(User, NotificationPreference.user_id == User.id)
            .filter(
                User.role == UserRole.STUDENT,
                NotificationPreference.weekly_digest == True,  # noqa: E712
            )
            .all()
        )

        for pref in student_prefs:
            student_id = str(pref.user_id)

            # Get all attendance records for the week
            records = (
                self.db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == pref.user_id,
                    AttendanceRecord.date >= week_start,
                    AttendanceRecord.date <= week_ending,
                )
                .all()
            )

            if not records:
                continue

            present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
            rate = (present / len(records)) * 100.0

            # Per-subject breakdown
            subject_map = {}
            for rec in records:
                sid = str(rec.schedule_id)
                if sid not in subject_map:
                    subject_map[sid] = {"total": 0, "present": 0}
                subject_map[sid]["total"] += 1
                if rec.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
                    subject_map[sid]["present"] += 1

            subject_breakdown = []
            for sid, data in subject_map.items():
                s_rate = (data["present"] / data["total"]) * 100.0 if data["total"] > 0 else 0
                subject_breakdown.append(
                    {
                        "schedule_id": sid,
                        "rate": round(s_rate, 1),
                        "attended": data["present"],
                        "total": data["total"],
                    }
                )

            digest = build_student_weekly_digest(
                attendance_rate=rate,
                classes_attended=present,
                classes_total=len(records),
                subject_breakdown=subject_breakdown,
            )

            if self.notification_service:
                try:
                    self.notification_service.create_persisted_notification(
                        user_id=student_id,
                        title="Weekly Attendance Summary",
                        message=digest["summary_text"],
                        notification_type="digest",
                        data=digest,
                    )
                except Exception as e:
                    logger.error(f"Failed to send weekly digest to {student_id}: {e}")

            # Send email digest if enabled
            if self.email_service and pref.email_enabled:
                try:
                    student = self.db.query(User).filter(User.id == pref.user_id).first()
                    if student and student.email:
                        # Enrich subject breakdown with names
                        enriched_breakdown = []
                        for s in subject_breakdown:
                            schedule = self.db.query(Schedule).filter(Schedule.id == s["schedule_id"]).first()
                            enriched_breakdown.append({
                                "subject_code": schedule.subject_code if schedule else "N/A",
                                "subject_name": schedule.subject_name if schedule else "Unknown",
                                "rate": s["rate"],
                                "attended": s["attended"],
                                "total": s["total"],
                            })
                        self.email_service.send_weekly_digest_email(
                            student_email=student.email,
                            student_name=f"{student.first_name} {student.last_name}",
                            digest_data={
                                "week_range": f"{week_start.strftime('%b %d')} – {week_ending.strftime('%b %d, %Y')}",
                                "overall_rate": rate,
                                "total_classes": len(records),
                                "classes_attended": present,
                                "subject_breakdown": enriched_breakdown,
                            },
                        )
                except Exception as e:
                    logger.error(f"Failed to send weekly digest email to {student_id}: {e}")

            created += 1

        logger.info(f"Generated {created} student weekly digests for week ending {week_ending}")
        return created
