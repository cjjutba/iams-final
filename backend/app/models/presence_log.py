"""
Presence Log Model

Stores individual scan results for continuous presence tracking.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import BIGINT, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PresenceLog(Base):
    """
    Presence log model

    Records individual scans during a class session.
    Used to track continuous presence and calculate presence score.

    Attributes:
        id: BigInteger primary key (auto-increment)
        attendance_id: Foreign key to attendance record
        scan_number: Sequential scan number (1, 2, 3, ...)
        scan_time: Timestamp of scan
        detected: Whether student was detected in this scan
        confidence: Face recognition confidence (if detected)
    """

    __tablename__ = "presence_logs"

    # Primary key (BigInteger for high volume, falls back to Integer on SQLite)
    # Using Integer().with_variant() to ensure autoincrement works on SQLite
    id = Column(Integer().with_variant(BIGINT, "postgresql"), primary_key=True, autoincrement=True)

    # Foreign key
    attendance_id = Column(UUID(as_uuid=True), ForeignKey("attendance_records.id"), nullable=False, index=True)

    # Scan details
    scan_number = Column(Integer, nullable=False)  # Sequential number
    scan_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    detected = Column(Boolean, nullable=False)
    confidence = Column(Float, nullable=True)  # 0-1 if detected, null if not detected

    # Relationships
    attendance_record = relationship("AttendanceRecord", backref="presence_logs")

    def __repr__(self):
        return f"<PresenceLog(id={self.id}, scan={self.scan_number}, detected={self.detected})>"
