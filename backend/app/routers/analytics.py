"""
Analytics Router

API endpoints for attendance analytics and reporting.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.anomaly_repository import AnomalyRepository
from app.services.analytics_service import AnalyticsService
from app.utils.dependencies import get_current_faculty, get_current_student, get_current_user

router = APIRouter()


# ----- Faculty Endpoints -----


@router.get("/class/{schedule_id}")
def get_class_overview(
    schedule_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Get overview statistics for a class."""
    svc = AnalyticsService(db)
    return svc.get_class_overview(schedule_id, start_date, end_date)


@router.get("/class/{schedule_id}/heatmap")
def get_class_heatmap(
    schedule_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Get daily attendance rates for heatmap visualization."""
    svc = AnalyticsService(db)
    return svc.get_attendance_heatmap(schedule_id, start_date, end_date)


@router.get("/class/{schedule_id}/ranking")
def get_class_ranking(
    schedule_id: str,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Rank students in a class by attendance rate."""
    svc = AnalyticsService(db)
    return svc.get_class_ranking(schedule_id)


@router.get("/at-risk")
def get_at_risk_students(
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Get at-risk students across all classes taught by the faculty."""
    svc = AnalyticsService(db)
    return svc.get_at_risk_students(str(current_user.id))


@router.get("/anomalies")
def get_anomalies(
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Get unresolved anomalies."""
    repo = AnomalyRepository(db)
    anomalies = repo.get_unresolved()
    return [
        {
            "id": str(a.id),
            "student_id": str(a.student_id),
            "anomaly_type": a.anomaly_type.value,
            "severity": a.severity,
            "description": a.description,
            "resolved": a.resolved,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in anomalies
    ]


@router.patch("/anomalies/{anomaly_id}/resolve")
def resolve_anomaly(
    anomaly_id: str,
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Mark an anomaly as resolved."""
    repo = AnomalyRepository(db)
    anomaly = repo.resolve(anomaly_id, str(current_user.id))
    if not anomaly:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Anomaly not found")
    return {"success": True, "resolved": True}


@router.get("/predictions/{schedule_id}")
def get_predictions(
    schedule_id: str,
    week_start: date | None = Query(None),
    current_user: User = Depends(get_current_faculty),
    db: Session = Depends(get_db),
):
    """Get attendance predictions for a schedule."""
    from app.repositories.prediction_repository import PredictionRepository

    repo = PredictionRepository(db)
    target = week_start or date.today()
    predictions = repo.get_by_schedule(schedule_id, target)
    return [
        {
            "student_id": str(p.student_id),
            "predicted_rate": p.predicted_rate,
            "trend": p.trend,
            "risk_level": p.risk_level.value,
        }
        for p in predictions
    ]


# ----- Student Endpoints -----


@router.get("/me/dashboard")
def get_student_dashboard(
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Get student self-dashboard data."""
    svc = AnalyticsService(db)
    return svc.get_student_dashboard(str(current_user.id))


@router.get("/me/subjects")
def get_student_subjects(
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Get per-subject attendance breakdown for the current student."""
    svc = AnalyticsService(db)
    return svc.get_student_subject_breakdown(str(current_user.id))


# ----- Admin Endpoints -----


@router.get("/system/metrics")
def get_system_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get system-wide metrics (admin only)."""
    svc = AnalyticsService(db)
    return svc.get_system_metrics()


@router.get("/system/daily-trend")
def get_daily_trend(
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get daily attendance trend (present/late/absent counts) for the last N days."""
    svc = AnalyticsService(db)
    return svc.get_daily_trend(days)


@router.get("/system/weekday-breakdown")
def get_weekday_breakdown(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get average attendance rate per day of the week."""
    svc = AnalyticsService(db)
    return svc.get_weekday_breakdown()
