"""
Notification Preference Model

Per-user notification preferences controlling which alerts they receive.
"""

from sqlalchemy import Boolean, Column, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class NotificationPreference(Base):
    """
    Notification preference model

    Controls which notification types a user receives.

    Attributes:
        user_id: FK to users (also PK, one per user)
        early_leave_alerts: Receive early leave notifications
        anomaly_alerts: Receive anomaly detection alerts
        attendance_confirmation: Student receives check-in confirmations
        low_attendance_warning: Receive low attendance warnings
        daily_digest: Receive daily summary (faculty)
        weekly_digest: Receive weekly summary (both roles)
        low_attendance_threshold: Threshold for low attendance warnings (%)
    """

    __tablename__ = "notification_preferences"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Alert types
    early_leave_alerts = Column(Boolean, default=True, nullable=False)
    anomaly_alerts = Column(Boolean, default=True, nullable=False)
    attendance_confirmation = Column(Boolean, default=True, nullable=False)
    low_attendance_warning = Column(Boolean, default=True, nullable=False)

    # Admin-facing alert categories (Phase 1 of notifications overhaul).
    # `audit_alerts` defaults to False because peer-admin audit notifications
    # are noisy in small teams — opt-in only.
    camera_alerts = Column(Boolean, nullable=False, default=True, server_default="true")
    ml_health_alerts = Column(Boolean, nullable=False, default=True, server_default="true")
    security_alerts = Column(Boolean, nullable=False, default=True, server_default="true")
    audit_alerts = Column(Boolean, nullable=False, default=False, server_default="false")
    schedule_conflict_alerts = Column(Boolean, nullable=False, default=True, server_default="true")
    face_alerts = Column(Boolean, nullable=False, default=True, server_default="true")
    daily_health_summary = Column(Boolean, nullable=False, default=False, server_default="false")

    # Digest types
    daily_digest = Column(Boolean, default=False, nullable=False)
    weekly_digest = Column(Boolean, default=True, nullable=False)

    # Email
    email_enabled = Column(Boolean, default=False, nullable=False)

    # Thresholds
    low_attendance_threshold = Column(Float, default=75.0, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="notification_preference", uselist=False)

    def __repr__(self):
        return f"<NotificationPreference(user_id={self.user_id})>"
