"""
Engagement Repository

Data access layer for EngagementScore operations.
"""

import uuid
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.engagement_score import EngagementScore


class EngagementRepository:
    """Repository for EngagementScore CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_attendance(self, attendance_id: str) -> Optional[EngagementScore]:
        """Get engagement score for an attendance record."""
        return self.db.query(EngagementScore).filter(
            EngagementScore.attendance_id == uuid.UUID(attendance_id)
        ).first()

    def create(self, attendance_id: str, **scores) -> EngagementScore:
        """Create engagement score record.

        Args:
            attendance_id: FK to attendance_records
            **scores: consistency_score, punctuality_score,
                      sustained_presence_score, confidence_avg,
                      engagement_score
        """
        score = EngagementScore(
            attendance_id=uuid.UUID(attendance_id),
            **scores,
        )
        self.db.add(score)
        self.db.commit()
        self.db.refresh(score)
        return score

    def upsert(self, attendance_id: str, **scores) -> EngagementScore:
        """Create or update engagement score for an attendance record."""
        existing = self.get_by_attendance(attendance_id)
        if existing:
            for k, v in scores.items():
                setattr(existing, k, v)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create(attendance_id, **scores)

    def get_by_student(
        self, student_id: str, limit: int = 20
    ) -> List[EngagementScore]:
        """Get recent engagement scores for a student (via attendance_records join)."""
        from app.models.attendance_record import AttendanceRecord
        return (
            self.db.query(EngagementScore)
            .join(AttendanceRecord, EngagementScore.attendance_id == AttendanceRecord.id)
            .filter(AttendanceRecord.student_id == uuid.UUID(student_id))
            .order_by(AttendanceRecord.date.desc())
            .limit(limit)
            .all()
        )
