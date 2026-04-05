"""
Engagement Score Model

Stores computed engagement metrics for each attendance record.
Derived from presence patterns, punctuality, and recognition confidence.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EngagementScore(Base):
    """
    Engagement score model

    Stores per-session engagement metrics computed from presence logs
    and attendance data.

    Attributes:
        id: UUID primary key
        attendance_id: Foreign key to attendance record (unique, one score per session)
        consistency_score: Score based on how consistently the student was detected (0-100)
        punctuality_score: Score based on arrival time relative to class start (0-100)
        sustained_presence_score: Score based on continuous presence without gaps (0-100)
        confidence_avg: Average face recognition confidence across scans (0-1)
        engagement_score: Overall composite engagement score (0-100)
        computed_at: When the score was computed
    """

    __tablename__ = "engagement_scores"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key (one engagement score per attendance record)
    attendance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Score components
    consistency_score = Column(Float, nullable=True)  # 0-100
    punctuality_score = Column(Float, nullable=True)  # 0-100
    sustained_presence_score = Column(Float, nullable=True)  # 0-100
    confidence_avg = Column(Float, nullable=True)  # 0-1

    # Composite score
    engagement_score = Column(Float, nullable=True)  # 0-100

    # Timestamps
    computed_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    attendance_record = relationship("AttendanceRecord", foreign_keys=[attendance_id])

    def __repr__(self):
        return f"<EngagementScore(id={self.id}, attendance_id={self.attendance_id}, score={self.engagement_score})>"
