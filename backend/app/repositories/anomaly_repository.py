"""
Anomaly Repository

Data access layer for AttendanceAnomaly operations.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.attendance_anomaly import AnomalyType, AttendanceAnomaly


class AnomalyRepository:
    """Repository for AttendanceAnomaly CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        student_id: str,
        anomaly_type: AnomalyType,
        severity: str,
        description: str,
        schedule_id: str | None = None,
        details: str | None = None,
        confidence: float | None = None,
    ) -> AttendanceAnomaly:
        """Create a new anomaly record."""
        anomaly = AttendanceAnomaly(
            student_id=uuid.UUID(student_id),
            schedule_id=uuid.UUID(schedule_id) if schedule_id else None,
            anomaly_type=anomaly_type,
            severity=severity,
            description=description,
            details=details,
            confidence=confidence,
        )
        self.db.add(anomaly)
        self.db.commit()
        self.db.refresh(anomaly)
        return anomaly

    def get_by_id(self, anomaly_id: str) -> AttendanceAnomaly | None:
        """Get anomaly by ID."""
        return self.db.query(AttendanceAnomaly).filter(AttendanceAnomaly.id == uuid.UUID(anomaly_id)).first()

    def get_unresolved(self, limit: int = 50, anomaly_type: AnomalyType | None = None) -> list[AttendanceAnomaly]:
        """Get unresolved anomalies, optionally filtered by type."""
        q = self.db.query(AttendanceAnomaly).filter(
            AttendanceAnomaly.resolved == False  # noqa: E712
        )
        if anomaly_type:
            q = q.filter(AttendanceAnomaly.anomaly_type == anomaly_type)
        return q.order_by(AttendanceAnomaly.detected_at.desc()).limit(limit).all()

    def get_by_student(self, student_id: str, limit: int = 20) -> list[AttendanceAnomaly]:
        """Get anomalies for a student."""
        return (
            self.db.query(AttendanceAnomaly)
            .filter(AttendanceAnomaly.student_id == uuid.UUID(student_id))
            .order_by(AttendanceAnomaly.detected_at.desc())
            .limit(limit)
            .all()
        )

    def resolve(self, anomaly_id: str, resolved_by: str) -> AttendanceAnomaly | None:
        """Mark an anomaly as resolved."""
        anomaly = self.get_by_id(anomaly_id)
        if anomaly:
            anomaly.resolved = True
            anomaly.resolved_by = uuid.UUID(resolved_by)
            anomaly.resolved_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(anomaly)
        return anomaly
