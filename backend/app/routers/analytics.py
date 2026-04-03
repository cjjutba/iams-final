"""
Analytics Router

Faculty analytics dashboard endpoints — class overviews, at-risk students, anomalies.
System-wide analytics for admin dashboard — metrics, trends, weekday breakdown.
All data is computed from existing attendance records and anomaly tables.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.attendance_anomaly import AttendanceAnomaly
from app.models.early_leave_event import EarlyLeaveEvent
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.analytics import (
    AnomalyItemResponse,
    AtRiskStudentResponse,
    ClassOverviewResponse,
)
from app.utils.dependencies import get_current_admin, get_current_faculty

router = APIRouter()


@router.get(
    "/class/{schedule_id}/overview",
    response_model=ClassOverviewResponse,
    status_code=status.HTTP_200_OK,
)
def get_class_overview(
    schedule_id: str,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    Get attendance overview for a single class/schedule.
    Computes average attendance rate, session count, enrolled count,
    early-leave count, and anomaly count from existing records.
    """
    from fastapi import HTTPException

    schedule_repo = ScheduleRepository(db)
    attendance_repo = AttendanceRepository(db)

    schedule = schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Faculty can only see their own schedules (admins see all)
    if current_user.role == UserRole.FACULTY and str(schedule.faculty_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    enrolled = schedule_repo.get_enrolled_students(schedule_id)
    total_enrolled = len(enrolled)

    # Get all attendance records for this schedule
    all_records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.schedule_id == schedule.id)
        .all()
    )

    # Count distinct session dates
    session_dates = {r.date for r in all_records}
    total_sessions = len(session_dates)

    # Average attendance rate across all records
    if all_records:
        present_or_late = sum(
            1 for r in all_records
            if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
        )
        avg_rate = (present_or_late / len(all_records)) * 100
    else:
        avg_rate = 0.0

    # Early leave count
    early_leave_count = (
        db.query(EarlyLeaveEvent)
        .join(AttendanceRecord, EarlyLeaveEvent.attendance_id == AttendanceRecord.id)
        .filter(AttendanceRecord.schedule_id == schedule.id)
        .count()
    )

    # Anomaly count
    anomaly_count = (
        db.query(AttendanceAnomaly)
        .filter(AttendanceAnomaly.schedule_id == schedule.id)
        .count()
    )

    return ClassOverviewResponse(
        schedule_id=schedule_id,
        subject_name=schedule.subject_name,
        subject_code=schedule.subject_code,
        day_of_week=schedule.day_of_week,
        start_time=str(schedule.start_time),
        end_time=str(schedule.end_time),
        average_attendance_rate=round(avg_rate, 1),
        total_sessions=total_sessions,
        total_enrolled=total_enrolled,
        early_leave_count=early_leave_count,
        anomaly_count=anomaly_count,
    )


@router.get(
    "/at-risk-students",
    response_model=list[AtRiskStudentResponse],
    status_code=status.HTTP_200_OK,
)
def get_at_risk_students(
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    Get students with low attendance across the faculty's schedules.
    A student is at-risk if their attendance rate < 80%.
    """
    schedule_repo = ScheduleRepository(db)

    if current_user.role == UserRole.ADMIN:
        schedules = schedule_repo.get_all()
    else:
        schedules = schedule_repo.get_by_faculty(str(current_user.id))

    results: list[AtRiskStudentResponse] = []

    for schedule in schedules:
        sid = str(schedule.id)
        enrolled = schedule_repo.get_enrolled_students(sid)

        # Get all records for this schedule
        all_records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.schedule_id == schedule.id)
            .all()
        )

        if not all_records:
            continue

        # Group records by student
        student_records: dict[str, list[AttendanceRecord]] = {}
        for r in all_records:
            key = str(r.student_id)
            student_records.setdefault(key, []).append(r)

        for student in enrolled:
            student_id = str(student.id)
            records = student_records.get(student_id, [])
            total = len(records)
            if total == 0:
                # Enrolled but no records — 0% attendance
                rate = 0.0
                missed = 0
            else:
                present_or_late = sum(
                    1 for r in records
                    if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
                )
                rate = (present_or_late / total) * 100
                missed = total - present_or_late

            if rate < 80:
                if rate < 40:
                    risk = "critical"
                elif rate < 60:
                    risk = "high"
                else:
                    risk = "moderate"

                # Count total sessions for this schedule
                session_dates = {r.date for r in all_records}
                sessions_total = len(session_dates)

                results.append(
                    AtRiskStudentResponse(
                        student_id=student_id,
                        student_name=f"{student.first_name} {student.last_name}",
                        schedule_id=sid,
                        subject_name=schedule.subject_name,
                        subject_code=schedule.subject_code,
                        attendance_rate=round(rate, 1),
                        risk_level=risk,
                        sessions_missed=missed,
                        sessions_total=sessions_total,
                    )
                )

    # Sort by attendance rate ascending (worst first)
    results.sort(key=lambda x: x.attendance_rate)
    return results


@router.get(
    "/anomalies",
    response_model=list[AnomalyItemResponse],
    status_code=status.HTTP_200_OK,
)
def get_anomalies(
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """
    Get attendance anomalies for the faculty's schedules.
    """
    schedule_repo = ScheduleRepository(db)

    if current_user.role == UserRole.ADMIN:
        schedules = schedule_repo.get_all()
    else:
        schedules = schedule_repo.get_by_faculty(str(current_user.id))

    schedule_ids = {s.id for s in schedules}
    schedule_map = {s.id: s for s in schedules}

    # Get anomalies for these schedules + global (no schedule_id)
    anomalies = (
        db.query(AttendanceAnomaly)
        .filter(
            (AttendanceAnomaly.schedule_id.in_(schedule_ids))
            | (AttendanceAnomaly.schedule_id.is_(None))
        )
        .order_by(AttendanceAnomaly.detected_at.desc())
        .limit(50)
        .all()
    )

    results = []
    for a in anomalies:
        subject_name = None
        if a.schedule_id and a.schedule_id in schedule_map:
            subject_name = schedule_map[a.schedule_id].subject_name

        results.append(
            AnomalyItemResponse(
                id=str(a.id),
                description=a.description,
                severity=a.severity,
                detected_at=a.detected_at.isoformat() if a.detected_at else "",
                subject_name=subject_name,
                resolved=a.resolved,
            )
        )

    return results


# =====================================================================
# System-wide analytics (admin dashboard)
# =====================================================================


@router.get("/system/metrics", status_code=status.HTTP_200_OK)
def get_system_metrics(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    System-wide metrics for the admin dashboard stat cards.
    Returns counts of students, faculty, schedules, attendance stats, anomalies, early leaves.
    """
    from app.models.student_record import StudentRecord
    from app.models.faculty_record import FacultyRecord

    total_students = db.query(StudentRecord).count()
    total_faculty = db.query(FacultyRecord).count()
    total_schedules = db.query(Schedule).count()
    total_attendance_records = db.query(AttendanceRecord).count()

    # Average attendance rate
    if total_attendance_records > 0:
        present_or_late = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE]))
            .count()
        )
        average_attendance_rate = round((present_or_late / total_attendance_records) * 100, 1)
    else:
        average_attendance_rate = 0.0

    total_anomalies = db.query(AttendanceAnomaly).count()
    unresolved_anomalies = (
        db.query(AttendanceAnomaly).filter(AttendanceAnomaly.resolved == False).count()  # noqa: E712
    )
    total_early_leaves = db.query(EarlyLeaveEvent).count()

    return {
        "success": True,
        "data": {
            "total_students": total_students,
            "total_faculty": total_faculty,
            "total_schedules": total_schedules,
            "total_attendance_records": total_attendance_records,
            "average_attendance_rate": average_attendance_rate,
            "total_anomalies": total_anomalies,
            "unresolved_anomalies": unresolved_anomalies,
            "total_early_leaves": total_early_leaves,
        },
    }


@router.get("/system/daily-trend", status_code=status.HTTP_200_OK)
def get_daily_trend(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Daily attendance counts (present/late/absent) for the last N days.
    Used by the admin dashboard line chart.
    """
    cutoff = date.today() - timedelta(days=days)

    rows = (
        db.query(
            AttendanceRecord.date,
            AttendanceRecord.status,
            func.count().label("cnt"),
        )
        .filter(AttendanceRecord.date >= cutoff)
        .group_by(AttendanceRecord.date, AttendanceRecord.status)
        .all()
    )

    # Aggregate by date
    daily: dict[date, dict[str, int]] = {}
    for r in rows:
        d = r.date
        if d not in daily:
            daily[d] = {"present": 0, "late": 0, "absent": 0}
        if r.status == AttendanceStatus.PRESENT:
            daily[d]["present"] += r.cnt
        elif r.status == AttendanceStatus.LATE:
            daily[d]["late"] += r.cnt
        elif r.status == AttendanceStatus.ABSENT:
            daily[d]["absent"] += r.cnt

    result = sorted(
        [{"date": d.isoformat(), **counts} for d, counts in daily.items()],
        key=lambda x: x["date"],
    )
    return result


@router.get("/system/weekday-breakdown", status_code=status.HTTP_200_OK)
def get_weekday_breakdown(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Average attendance rate per weekday (Mon-Sun).
    Used by the admin dashboard bar chart.
    """
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    rows = (
        db.query(
            func.extract("dow", AttendanceRecord.date).label("dow"),
            AttendanceRecord.status,
            func.count().label("cnt"),
        )
        .group_by("dow", AttendanceRecord.status)
        .all()
    )

    totals: dict[int, int] = {}
    present: dict[int, int] = {}
    for r in rows:
        dow = int(r.dow)  # PostgreSQL: 0=Sun, 1=Mon, ..., 6=Sat
        totals[dow] = totals.get(dow, 0) + r.cnt
        if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
            present[dow] = present.get(dow, 0) + r.cnt

    # Map PostgreSQL dow (0=Sun) to Monday-first ordering
    pg_to_py = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 0: 6}
    result = []
    for pg_dow, py_idx in sorted(pg_to_py.items(), key=lambda x: x[1]):
        total = totals.get(pg_dow, 0)
        pres = present.get(pg_dow, 0)
        rate = round((pres / total) * 100, 1) if total > 0 else 0.0
        result.append({"day": day_names[py_idx], "rate": rate})

    return result


@router.patch(
    "/anomalies/{anomaly_id}/resolve",
    status_code=status.HTTP_200_OK,
)
def resolve_anomaly(
    anomaly_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Mark an attendance anomaly as resolved."""
    anomaly = db.query(AttendanceAnomaly).filter(AttendanceAnomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.resolved = True
    anomaly.resolved_by = current_user.id
    anomaly.resolved_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "message": "Anomaly resolved"}
