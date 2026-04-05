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
