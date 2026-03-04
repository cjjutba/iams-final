"""
Analytics Service

Read-only aggregation queries over attendance, engagement, anomaly,
and prediction tables.
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import logger
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.engagement_score import EngagementScore
from app.models.attendance_anomaly import AttendanceAnomaly
from app.models.attendance_prediction import AttendancePrediction, RiskLevel
from app.models.early_leave_event import EarlyLeaveEvent
from app.models.enrollment import Enrollment
from app.models.schedule import Schedule
from app.models.user import User, UserRole


class AnalyticsService:
    """Read-only analytics queries."""

    def __init__(self, db: Session):
        self.db = db

    # ----- Faculty Analytics -----

    def get_class_overview(
        self,
        schedule_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get overview statistics for a class."""
        import uuid
        sid = uuid.UUID(schedule_id)
        schedule = self.db.query(Schedule).filter(Schedule.id == sid).first()
        if not schedule:
            return {}

        q = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.schedule_id == sid
        )
        if start_date:
            q = q.filter(AttendanceRecord.date >= start_date)
        if end_date:
            q = q.filter(AttendanceRecord.date <= end_date)

        records = q.all()
        if not records:
            return {
                "schedule_id": schedule_id,
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "total_sessions": 0,
                "average_attendance_rate": 0.0,
                "total_enrolled": 0,
                "early_leave_count": 0,
                "anomaly_count": 0,
            }

        # Unique session dates
        session_dates = set(r.date for r in records)
        present_count = sum(
            1 for r in records
            if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
        )
        rate = (present_count / len(records)) * 100.0 if records else 0

        enrolled = self.db.query(func.count(Enrollment.id)).filter(
            Enrollment.schedule_id == sid
        ).scalar() or 0

        early_leaves = self.db.query(func.count(EarlyLeaveEvent.id)).join(
            AttendanceRecord, EarlyLeaveEvent.attendance_id == AttendanceRecord.id
        ).filter(AttendanceRecord.schedule_id == sid).scalar() or 0

        anomalies = self.db.query(func.count(AttendanceAnomaly.id)).filter(
            AttendanceAnomaly.schedule_id == sid
        ).scalar() or 0

        return {
            "schedule_id": schedule_id,
            "subject_code": schedule.subject_code,
            "subject_name": schedule.subject_name,
            "total_sessions": len(session_dates),
            "average_attendance_rate": round(rate, 1),
            "total_enrolled": enrolled,
            "early_leave_count": early_leaves,
            "anomaly_count": anomalies,
        }

    def get_class_ranking(self, schedule_id: str) -> List[Dict[str, Any]]:
        """Rank students in a class by attendance rate."""
        import uuid
        sid = uuid.UUID(schedule_id)

        enrollments = self.db.query(Enrollment).filter(
            Enrollment.schedule_id == sid
        ).all()

        rankings = []
        for enrollment in enrollments:
            student = self.db.query(User).filter(User.id == enrollment.student_id).first()
            if not student:
                continue

            records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == enrollment.student_id,
                AttendanceRecord.schedule_id == sid,
            ).all()

            total = len(records)
            present = sum(
                1 for r in records
                if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
            )
            rate = (present / total) * 100.0 if total > 0 else 0.0

            # Get average engagement score
            eng_scores = (
                self.db.query(EngagementScore)
                .join(AttendanceRecord, EngagementScore.attendance_id == AttendanceRecord.id)
                .filter(
                    AttendanceRecord.student_id == enrollment.student_id,
                    AttendanceRecord.schedule_id == sid,
                )
                .all()
            )
            avg_engagement = None
            if eng_scores:
                avg_engagement = round(
                    sum(e.engagement_score for e in eng_scores) / len(eng_scores), 1
                )

            rankings.append({
                "student_id": str(enrollment.student_id),
                "student_name": f"{student.first_name} {student.last_name}",
                "student_number": student.student_id,
                "attendance_rate": round(rate, 1),
                "sessions_attended": present,
                "sessions_total": total,
                "engagement_score": avg_engagement,
            })

        rankings.sort(key=lambda x: x["attendance_rate"], reverse=True)
        return rankings

    def get_at_risk_students(self, faculty_id: str) -> List[Dict[str, Any]]:
        """Get at-risk students across all classes taught by faculty."""
        import uuid
        schedules = self.db.query(Schedule).filter(
            Schedule.faculty_id == uuid.UUID(faculty_id)
        ).all()

        at_risk = []
        for schedule in schedules:
            predictions = (
                self.db.query(AttendancePrediction)
                .filter(
                    AttendancePrediction.schedule_id == schedule.id,
                    AttendancePrediction.risk_level.in_([
                        RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MODERATE
                    ]),
                )
                .order_by(AttendancePrediction.predicted_rate.asc())
                .all()
            )

            for pred in predictions:
                student = self.db.query(User).filter(User.id == pred.student_id).first()
                if not student:
                    continue

                # Get current actual rate
                records = self.db.query(AttendanceRecord).filter(
                    AttendanceRecord.student_id == pred.student_id,
                    AttendanceRecord.schedule_id == schedule.id,
                ).all()
                total = len(records)
                present = sum(
                    1 for r in records
                    if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
                )
                current_rate = (present / total) * 100.0 if total > 0 else 0.0

                at_risk.append({
                    "student_id": str(pred.student_id),
                    "student_name": f"{student.first_name} {student.last_name}",
                    "student_number": student.student_id,
                    "schedule_id": str(schedule.id),
                    "subject_code": schedule.subject_code,
                    "current_rate": round(current_rate, 1),
                    "predicted_rate": round(pred.predicted_rate, 1),
                    "risk_level": pred.risk_level.value,
                    "trend": pred.trend,
                })

        at_risk.sort(key=lambda x: x["current_rate"])
        return at_risk

    def get_attendance_heatmap(
        self, schedule_id: str, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get daily attendance rates for heatmap visualization."""
        import uuid
        sid = uuid.UUID(schedule_id)

        q = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.schedule_id == sid
        )
        if start_date:
            q = q.filter(AttendanceRecord.date >= start_date)
        if end_date:
            q = q.filter(AttendanceRecord.date <= end_date)

        records = q.all()

        # Group by date
        by_date: Dict[date, list] = {}
        for rec in records:
            by_date.setdefault(rec.date, []).append(rec)

        heatmap = []
        for d, recs in sorted(by_date.items()):
            present = sum(
                1 for r in recs
                if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
            )
            heatmap.append({
                "date": d.isoformat(),
                "attendance_rate": round((present / len(recs)) * 100.0, 1),
                "total_students": len(recs),
                "present_count": present,
            })

        return heatmap

    # ----- Student Analytics -----

    def get_student_dashboard(self, student_id: str) -> Dict[str, Any]:
        """Get student self-dashboard data."""
        import uuid
        uid = uuid.UUID(student_id)

        records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.student_id == uid
        ).all()

        total = len(records)
        present = sum(
            1 for r in records
            if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
        )
        rate = (present / total) * 100.0 if total > 0 else 0.0

        # Current streak
        sorted_recs = sorted(records, key=lambda r: r.date, reverse=True)
        streak = 0
        for rec in sorted_recs:
            if rec.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
                streak += 1
            else:
                break

        # Average engagement
        eng_scores = (
            self.db.query(EngagementScore)
            .join(AttendanceRecord, EngagementScore.attendance_id == AttendanceRecord.id)
            .filter(AttendanceRecord.student_id == uid)
            .all()
        )
        avg_engagement = None
        if eng_scores:
            avg_engagement = round(
                sum(e.engagement_score for e in eng_scores) / len(eng_scores), 1
            )

        # Per-subject summary
        schedules_map: Dict[str, dict] = {}
        for rec in records:
            sid = str(rec.schedule_id)
            if sid not in schedules_map:
                schedules_map[sid] = {"total": 0, "present": 0, "schedule_id": sid}
            schedules_map[sid]["total"] += 1
            if rec.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
                schedules_map[sid]["present"] += 1

        subjects = []
        for data in schedules_map.values():
            s_rate = (data["present"] / data["total"]) * 100.0 if data["total"] > 0 else 0
            subjects.append({
                "schedule_id": data["schedule_id"],
                "rate": round(s_rate, 1),
                "attended": data["present"],
                "total": data["total"],
            })

        return {
            "overall_rate": round(rate, 1),
            "classes_attended": present,
            "classes_total": total,
            "current_streak": streak,
            "average_engagement": avg_engagement,
            "subjects": subjects,
        }

    def get_student_subject_breakdown(self, student_id: str) -> List[Dict[str, Any]]:
        """Get per-subject attendance breakdown for a student."""
        import uuid
        uid = uuid.UUID(student_id)

        enrollments = self.db.query(Enrollment).filter(
            Enrollment.student_id == uid
        ).all()

        breakdown = []
        for enrollment in enrollments:
            schedule = self.db.query(Schedule).filter(
                Schedule.id == enrollment.schedule_id
            ).first()
            if not schedule:
                continue

            records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == uid,
                AttendanceRecord.schedule_id == schedule.id,
            ).all()

            total = len(records)
            present = sum(
                1 for r in records
                if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
            )
            rate = (present / total) * 100.0 if total > 0 else 0.0

            breakdown.append({
                "schedule_id": str(schedule.id),
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "attendance_rate": round(rate, 1),
                "sessions_attended": present,
                "sessions_total": total,
            })

        return breakdown

    # ----- Admin Analytics -----

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics."""
        total_students = self.db.query(func.count(User.id)).filter(
            User.role == UserRole.STUDENT
        ).scalar() or 0

        total_faculty = self.db.query(func.count(User.id)).filter(
            User.role == UserRole.FACULTY
        ).scalar() or 0

        total_schedules = self.db.query(func.count(Schedule.id)).scalar() or 0

        total_records = self.db.query(func.count(AttendanceRecord.id)).scalar() or 0

        present_records = self.db.query(func.count(AttendanceRecord.id)).filter(
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE])
        ).scalar() or 0
        avg_rate = (present_records / total_records) * 100.0 if total_records > 0 else 0

        total_anomalies = self.db.query(func.count(AttendanceAnomaly.id)).scalar() or 0
        unresolved = self.db.query(func.count(AttendanceAnomaly.id)).filter(
            AttendanceAnomaly.resolved == False  # noqa: E712
        ).scalar() or 0

        total_early_leaves = self.db.query(func.count(EarlyLeaveEvent.id)).scalar() or 0

        return {
            "total_students": total_students,
            "total_faculty": total_faculty,
            "total_schedules": total_schedules,
            "total_attendance_records": total_records,
            "average_attendance_rate": round(avg_rate, 1),
            "total_anomalies": total_anomalies,
            "unresolved_anomalies": unresolved,
            "total_early_leaves": total_early_leaves,
        }
