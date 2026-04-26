"""
Email Service — Resend REST API integration.

Sends transactional emails for notification events (check-in, early-leave,
low-attendance, broadcast, daily/weekly digest).  Uses httpx.AsyncClient
to call Resend's REST API directly — no SDK dependency.
"""

import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


# ── HTML templates ───────────────────────────────────────────────


def _base_html(title: str, body: str) -> str:
    """Wrap body in a minimal branded HTML email layout."""
    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto;padding:24px">
  <h2 style="margin:0 0 16px">{title}</h2>
  {body}
  <hr style="margin:32px 0 12px;border:none;border-top:1px solid #e5e5e5">
  <p style="font-size:12px;color:#888">IAMS — Intelligent Attendance Monitoring System</p>
</div>"""


_TEMPLATES: dict[str, callable] = {}


def _template(name: str):
    def decorator(fn):
        _TEMPLATES[name] = fn
        return fn

    return decorator


@_template("check_in")
def _check_in(ctx: dict) -> tuple[str, str]:
    subject = f"Attendance Confirmed — {ctx.get('subject_code', 'Class')}"
    body = _base_html(
        "You're Marked Present",
        f"<p>Hi {ctx.get('student_name', 'Student')},</p>"
        f"<p>You have been marked <strong>{ctx.get('status', 'present')}</strong> "
        f"for <strong>{ctx.get('subject_code', '')} {ctx.get('subject_name', '')}</strong> "
        f"at {ctx.get('check_in_time', '')}.</p>",
    )
    return subject, body


@_template("early_leave")
def _early_leave(ctx: dict) -> tuple[str, str]:
    subject = f"Early Leave Alert — {ctx.get('student_name', 'Student')}"
    body = _base_html(
        "Early Leave Detected",
        f"<p>{ctx.get('student_name', 'A student')} appears to have left "
        f"<strong>{ctx.get('subject_code', 'class')}</strong> early.</p>"
        f"<p>Last seen: {ctx.get('last_seen_at', 'N/A')}<br>"
        f"Consecutive misses: {ctx.get('consecutive_misses', '?')}<br>"
        f"Severity: {ctx.get('severity', 'medium')}</p>",
    )
    return subject, body


@_template("low_attendance")
def _low_attendance(ctx: dict) -> tuple[str, str]:
    subject = f"Low Attendance Warning — {ctx.get('subject_code', 'Class')}"
    body = _base_html(
        "Your Attendance Is Low",
        f"<p>Hi {ctx.get('student_name', 'Student')},</p>"
        f"<p>Your attendance for <strong>{ctx.get('subject_code', '')}</strong> "
        f"is currently at <strong>{ctx.get('presence_score', '?')}%</strong>, "
        f"below the {ctx.get('threshold', 75)}% threshold.</p>"
        f"<p>Please ensure consistent attendance.</p>",
    )
    return subject, body


@_template("broadcast")
def _broadcast(ctx: dict) -> tuple[str, str]:
    subject = ctx.get("title", "IAMS Announcement")
    body = _base_html(subject, f"<p>{ctx.get('message', '')}</p>")
    return subject, body


@_template("daily_digest")
def _daily_digest(ctx: dict) -> tuple[str, str]:
    date_str = ctx.get("date", datetime.now().strftime("%B %d, %Y"))
    subject = f"Daily Attendance Summary — {date_str}"
    rows = ctx.get("rows_html", "<p>No attendance data for today.</p>")
    body = _base_html("Daily Attendance Summary", rows)
    return subject, body


@_template("weekly_digest")
def _weekly_digest(ctx: dict) -> tuple[str, str]:
    week = ctx.get("week_label", "This Week")
    subject = f"Weekly Attendance Summary — {week}"
    rows = ctx.get("rows_html", "<p>No attendance data for this week.</p>")
    body = _base_html("Weekly Attendance Summary", rows)
    return subject, body


@_template("generic")
def _generic(ctx: dict) -> tuple[str, str]:
    subject = ctx.get("subject", "IAMS Notification")
    body = _base_html(
        ctx.get("title", subject),
        f"<p>{ctx.get('message', '')}</p>",
    )
    return subject, body


# ── User lifecycle templates ─────────────────────────────────────


@_template("user_welcome")
def _user_welcome(ctx: dict) -> tuple[str, str]:
    subject = "Welcome to IAMS"
    body = _base_html(
        "Welcome to IAMS",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>Your IAMS account has been created successfully.</p>"
        f"<p><strong>Username:</strong> {ctx.get('username', 'N/A')}<br>"
        f"<strong>Role:</strong> {ctx.get('role', 'user')}</p>"
        f"<p>Please contact an administrator if you have not received your "
        f"initial password separately.</p>",
    )
    return subject, body


@_template("user_deactivated")
def _user_deactivated(ctx: dict) -> tuple[str, str]:
    subject = "IAMS account deactivated"
    body = _base_html(
        "Account Deactivated",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>Your IAMS account has been deactivated. You will no longer be "
        f"able to log in.</p>"
        f"<p>If you believe this is in error, please contact an "
        f"administrator.</p>",
    )
    return subject, body


@_template("user_reactivated")
def _user_reactivated(ctx: dict) -> tuple[str, str]:
    subject = "IAMS account reactivated"
    body = _base_html(
        "Account Reactivated",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>Your IAMS account has been reactivated. You may now log in "
        f"normally.</p>",
    )
    return subject, body


@_template("user_role_changed")
def _user_role_changed(ctx: dict) -> tuple[str, str]:
    subject = "IAMS account role changed"
    body = _base_html(
        "Account Role Updated",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>Your account role has been changed from "
        f"<strong>{ctx.get('old_role', 'user')}</strong> to "
        f"<strong>{ctx.get('new_role', 'user')}</strong>.</p>"
        f"<p>If you have questions about this change, please contact an "
        f"administrator.</p>",
    )
    return subject, body


# ── Schedule lifecycle templates ─────────────────────────────────


@_template("schedule_assigned")
def _schedule_assigned(ctx: dict) -> tuple[str, str]:
    subject = f"Schedule assigned: {ctx.get('subject_code', 'New Class')}"
    body = _base_html(
        "Schedule Assigned",
        f"<p>You have been assigned a new teaching schedule.</p>"
        f"<p><strong>Subject:</strong> {ctx.get('subject_code', '')}<br>"
        f"<strong>Day:</strong> {ctx.get('day_of_week', 'TBD')}<br>"
        f"<strong>Time:</strong> {ctx.get('start_time', '')} – "
        f"{ctx.get('end_time', '')}<br>"
        f"<strong>Room:</strong> {ctx.get('room_name', 'TBD')}</p>",
    )
    return subject, body


@_template("schedule_updated")
def _schedule_updated(ctx: dict) -> tuple[str, str]:
    subject = f"Schedule updated: {ctx.get('subject_code', 'Class')}"
    changes = ctx.get("changes") or []
    if isinstance(changes, list) and changes:
        rows = "".join(f"<li>{c}</li>" for c in changes)
        change_block = f"<ul>{rows}</ul>"
    else:
        change_block = "<p>Schedule details were updated.</p>"
    body = _base_html(
        "Schedule Updated",
        f"<p>The schedule for <strong>{ctx.get('subject_code', '')}</strong> "
        f"has been updated:</p>"
        f"{change_block}",
    )
    return subject, body


@_template("schedule_deleted")
def _schedule_deleted(ctx: dict) -> tuple[str, str]:
    subject = f"Class cancelled: {ctx.get('subject_code', 'Class')}"
    body = _base_html(
        "Class Cancelled",
        f"<p>The class <strong>{ctx.get('subject_code', '')}</strong> "
        f"scheduled on {ctx.get('day_of_week', 'TBD')} "
        f"({ctx.get('start_time', '')} – {ctx.get('end_time', '')}) "
        f"has been deleted.</p>"
        f"<p>If you have questions, please contact an administrator.</p>",
    )
    return subject, body


@_template("enrollment_added")
def _enrollment_added(ctx: dict) -> tuple[str, str]:
    subject = f"Enrolled in {ctx.get('subject_code', 'a class')}"
    body = _base_html(
        "Enrollment Confirmed",
        f"<p>You have been enrolled in "
        f"<strong>{ctx.get('subject_code', '')}</strong>.</p>"
        f"<p><strong>Day:</strong> {ctx.get('day_of_week', 'TBD')}<br>"
        f"<strong>Time:</strong> {ctx.get('start_time', '')} – "
        f"{ctx.get('end_time', '')}<br>"
        f"<strong>Room:</strong> {ctx.get('room_name', 'TBD')}</p>",
    )
    return subject, body


@_template("enrollment_removed")
def _enrollment_removed(ctx: dict) -> tuple[str, str]:
    subject = f"Unenrolled from {ctx.get('subject_code', 'a class')}"
    body = _base_html(
        "Enrollment Removed",
        f"<p>You have been removed from "
        f"<strong>{ctx.get('subject_code', '')}</strong>.</p>"
        f"<p>If this is unexpected, please contact an administrator.</p>",
    )
    return subject, body


# ── Face-registration lifecycle templates ────────────────────────


@_template("face_approved")
def _face_approved(ctx: dict) -> tuple[str, str]:
    subject = "Face registration approved"
    body = _base_html(
        "Face Registration Approved",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>Your face registration has been approved. You are now ready "
        f"for automatic attendance recognition during your scheduled "
        f"classes.</p>",
    )
    return subject, body


@_template("face_rejected")
def _face_rejected(ctx: dict) -> tuple[str, str]:
    subject = "Face registration needs attention"
    reason = ctx.get("reason") or "The submitted captures did not meet quality requirements."
    body = _base_html(
        "Face Registration Rejected",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>Your face registration was not approved.</p>"
        f"<p><strong>Reason:</strong> {reason}</p>"
        f"<p>Please re-register your face from the IAMS student app at "
        f"your earliest convenience.</p>",
    )
    return subject, body


@_template("face_re_registration_required")
def _face_re_registration_required(ctx: dict) -> tuple[str, str]:
    subject = "Face re-registration required"
    body = _base_html(
        "Face Re-registration Required",
        f"<p>Hi {ctx.get('user_name', 'there')},</p>"
        f"<p>An administrator has reset your face registration. To continue "
        f"using automatic attendance recognition, please re-register your "
        f"face from the IAMS student app.</p>",
    )
    return subject, body


# ── Service ──────────────────────────────────────────────────────


class EmailService:
    """Sends transactional emails via Resend REST API."""

    def __init__(self):
        self._from = settings.RESEND_FROM_EMAIL
        self._api_key = settings.RESEND_API_KEY

    async def send_notification_email(
        self,
        to_email: str,
        to_name: str,
        template: str,
        context: dict | None = None,
    ) -> bool:
        """
        Render a template and send a single email.

        Returns True on success, False on failure (never raises).
        """
        if not settings.EMAIL_ENABLED or not self._api_key:
            return False

        ctx = context or {}
        renderer = _TEMPLATES.get(template, _TEMPLATES["generic"])
        subject, html = renderer(ctx)

        return await self._send(to_email, subject, html)

    async def send_broadcast_email(
        self,
        recipients: list[str],
        title: str,
        message: str,
    ) -> int:
        """
        Send a broadcast email to multiple recipients.

        Returns count of successfully sent emails.
        """
        if not settings.EMAIL_ENABLED or not self._api_key:
            return 0

        subject, html = _TEMPLATES["broadcast"]({"title": title, "message": message})
        sent = 0
        for email in recipients:
            if await self._send(email, subject, html):
                sent += 1
        return sent

    async def _send(self, to: str, subject: str, html: str) -> bool:
        """Low-level Resend API call."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self._from,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                    },
                )
                if resp.status_code >= 400:
                    logger.error(f"Resend API error ({resp.status_code}): {resp.text}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Email send failed to {to}: {e}")
            return False
