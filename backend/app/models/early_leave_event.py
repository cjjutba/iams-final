"""
Early Leave Event Model

Records when a student is detected leaving class early.
Tracks return detection and context-aware severity.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EarlyLeaveEvent(Base):
    """
    Early leave event model

    Records when a student is flagged for leaving class early.
    Created when consecutive_misses >= threshold.

    Attributes:
        id: UUID primary key
        attendance_id: Foreign key to attendance record
        detected_at: When early leave was first detected
        last_seen_at: Last time student was detected
        consecutive_misses: Number of consecutive scans missed
        notified: Whether faculty was notified
        notified_at: When notification was sent
        returned: Whether student returned after early leave
        returned_at: When student was re-detected
        absence_duration_seconds: Duration of absence in seconds
        context_severity: Severity based on when in class the leave occurred
    """

    __tablename__ = "early_leave_events"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key
    attendance_id = Column(
        UUID(as_uuid=True), ForeignKey("attendance_records.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Event details
    detected_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    consecutive_misses = Column(Integer, nullable=False)

    # Notification status
    notified = Column(Boolean, default=False, nullable=False)
    notified_at = Column(DateTime, nullable=True)

    # Return tracking
    returned = Column(Boolean, default=False, nullable=False)
    returned_at = Column(DateTime, nullable=True)
    absence_duration_seconds = Column(Integer, nullable=True)

    # Context-aware severity: "low" (near end), "medium" (mid-class), "high" (near start)
    context_severity = Column(String(20), nullable=True)

    # Relationships
    attendance_record = relationship("AttendanceRecord", back_populates="early_leave_events")

    def __repr__(self):
        return f"<EarlyLeaveEvent(id={self.id}, attendance_id={self.attendance_id}, misses={self.consecutive_misses}, severity={self.context_severity})>"
