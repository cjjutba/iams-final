"""
Email Service

Handles transactional email delivery via Resend SDK.
All methods are fail-safe: email errors are logged but never propagate.
"""

from datetime import datetime

import resend

from app.config import logger, settings
from app.services.email_templates import (
    render_broadcast,
    render_daily_digest,
    render_early_leave,
    render_low_attendance,
    render_weekly_digest,
)


class EmailService:
    """Transactional email service using Resend."""

    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY

    def _send(self, to: str | list[str], subject: str, html: str) -> bool:
        """
        Core send method. Returns True on success, False on failure.
        """
        if not settings.EMAIL_ENABLED or not settings.RESEND_API_KEY:
            logger.debug("Email disabled or no API key — skipping send")
            return False

        try:
            params = {
                "from": settings.RESEND_FROM_EMAIL,
                "to": to if isinstance(to, list) else [to],
                "subject": subject,
                "html": html,
            }
            resend.Emails.send(params)
            logger.info(f"Email sent: subject='{subject}' to={to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_early_leave_email(
        self,
        faculty_email: str,
        student_name: str,
        subject_code: str,
        subject_name: str,
        detected_at: datetime,
        consecutive_misses: int = 3,
    ) -> bool:
        """Send early leave alert email to faculty."""
        html = render_early_leave(
            student_name=student_name,
            subject_code=subject_code,
            subject_name=subject_name,
            detected_at=detected_at.strftime("%B %d, %Y at %I:%M %p"),
            consecutive_misses=consecutive_misses,
        )
        return self._send(
            to=faculty_email,
            subject=f"[IAMS] Early Leave Alert: {student_name} — {subject_code}",
            html=html,
        )

    def send_daily_digest_email(self, faculty_email: str, faculty_name: str, digest_data: dict) -> bool:
        """Send daily digest email to faculty."""
        html = render_daily_digest(
            faculty_name=faculty_name,
            date=digest_data.get("date", ""),
            total_sessions=digest_data.get("total_sessions", 0),
            avg_attendance_rate=digest_data.get("avg_attendance_rate", 0),
            early_leaves=digest_data.get("early_leaves", 0),
            anomalies=digest_data.get("anomalies", 0),
            session_details=digest_data.get("session_details", []),
        )
        return self._send(
            to=faculty_email,
            subject=f"[IAMS] Daily Attendance Summary — {digest_data.get('date', '')}",
            html=html,
        )

    def send_weekly_digest_email(self, student_email: str, student_name: str, digest_data: dict) -> bool:
        """Send weekly digest email to student."""
        html = render_weekly_digest(
            student_name=student_name,
            week_range=digest_data.get("week_range", ""),
            overall_rate=digest_data.get("overall_rate", 0),
            total_classes=digest_data.get("total_classes", 0),
            classes_attended=digest_data.get("classes_attended", 0),
            subject_breakdown=digest_data.get("subject_breakdown", []),
        )
        return self._send(
            to=student_email,
            subject=f"[IAMS] Weekly Attendance Summary — {digest_data.get('week_range', '')}",
            html=html,
        )

    def send_low_attendance_email(
        self,
        student_email: str,
        student_name: str,
        subject_name: str,
        subject_code: str,
        current_rate: float,
        threshold: float,
    ) -> bool:
        """Send low attendance warning email to student."""
        html = render_low_attendance(
            student_name=student_name,
            subject_name=subject_name,
            subject_code=subject_code,
            current_rate=current_rate,
            threshold=threshold,
        )
        return self._send(
            to=student_email,
            subject=f"[IAMS] Low Attendance Warning: {subject_code}",
            html=html,
        )

    def send_broadcast_email(self, recipients: list[str], title: str, message: str) -> bool:
        """Send broadcast notification email to a list of recipients."""
        html = render_broadcast(title=title, message=message)
        # Resend supports batch sending; send individually to avoid showing all recipients
        success_count = 0
        for email in recipients:
            if self._send(to=email, subject=f"[IAMS] {title}", html=html):
                success_count += 1
        logger.info(f"Broadcast email sent to {success_count}/{len(recipients)} recipients")
        return success_count > 0
