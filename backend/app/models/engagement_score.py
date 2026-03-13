"""
Engagement Score Model

Stores computed engagement metrics for each attendance session.
Provides deeper insight than simple present/absent by measuring
consistency, punctuality, sustained presence, and recognition confidence.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EngagementScore(Base):
    """
    Engagement score for a single attendance session.

    Attributes:
        id: UUID primary key
        attendance_id: FK to attendance_records (unique — one score per session)
        consistency_score: Detection gap regularity (0-100)
        punctuality_score: Arrival timeliness (0-100)
        sustained_presence_score: Longest unbroken detection streak ratio (0-100)
        confidence_avg: Average face recognition confidence across session
        engagement_score: Weighted composite score (0-100)
        computed_at: When the score was computed
    """

    __tablename__ = "engagement_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attendance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Component scores (0-100)
    consistency_score = Column(Float, default=0.0, nullable=False)
    punctuality_score = Column(Float, default=0.0, nullable=False)
    sustained_presence_score = Column(Float, default=0.0, nullable=False)

    # Recognition confidence average
    confidence_avg = Column(Float, nullable=True)

    # Composite weighted score (0-100)
    engagement_score = Column(Float, default=0.0, nullable=False)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    attendance = relationship("AttendanceRecord", backref="engagement")

    __table_args__ = (Index("ix_engagement_scores_attendance_id", "attendance_id"),)

    def __repr__(self):
        return f"<EngagementScore(id={self.id}, attendance_id={self.attendance_id}, score={self.engagement_score:.1f})>"
