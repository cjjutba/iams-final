"""
Email Templates

Pure functions returning HTML strings for transactional email notifications.
All templates use inline CSS for email client compatibility.
"""


def _base_layout(content: str) -> str:
    """Wrap content in the shared JRMSU-branded email layout."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background-color:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
<!-- Header -->
<tr><td style="background-color:#18181b;padding:24px 32px;">
<h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;letter-spacing:-0.02em;">IAMS</h1>
<p style="margin:4px 0 0;color:#a1a1aa;font-size:12px;">Intelligent Attendance Monitoring System &mdash; JRMSU</p>
</td></tr>
<!-- Body -->
<tr><td style="padding:32px;">
{content}
</td></tr>
<!-- Footer -->
<tr><td style="padding:20px 32px;background-color:#fafafa;border-top:1px solid #e4e4e7;">
<p style="margin:0;color:#71717a;font-size:11px;text-align:center;">
This is an automated message from IAMS. Do not reply to this email.<br>
Jose Rizal Memorial State University &copy; 2026
</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def render_early_leave(
    student_name: str,
    subject_code: str,
    subject_name: str,
    detected_at: str,
    consecutive_misses: int = 3,
) -> str:
    """Render early leave alert email for faculty."""
    content = f"""
<div style="margin-bottom:24px;">
<span style="display:inline-block;padding:4px 12px;background-color:#fef2f2;color:#dc2626;font-size:12px;font-weight:600;border-radius:9999px;text-transform:uppercase;letter-spacing:0.05em;">Early Leave Alert</span>
</div>
<p style="margin:0 0 16px;color:#18181b;font-size:16px;line-height:1.5;">
A student has been flagged for leaving class early.
</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f9fafb;border-radius:8px;margin-bottom:24px;">
<tr><td style="padding:20px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="padding:6px 0;color:#71717a;font-size:13px;width:140px;">Student</td>
<td style="padding:6px 0;color:#18181b;font-size:14px;font-weight:500;">{student_name}</td>
</tr>
<tr>
<td style="padding:6px 0;color:#71717a;font-size:13px;">Subject</td>
<td style="padding:6px 0;color:#18181b;font-size:14px;font-weight:500;">{subject_code} &mdash; {subject_name}</td>
</tr>
<tr>
<td style="padding:6px 0;color:#71717a;font-size:13px;">Detected At</td>
<td style="padding:6px 0;color:#18181b;font-size:14px;font-weight:500;">{detected_at}</td>
</tr>
<tr>
<td style="padding:6px 0;color:#71717a;font-size:13px;">Missed Scans</td>
<td style="padding:6px 0;color:#dc2626;font-size:14px;font-weight:600;">{consecutive_misses} consecutive</td>
</tr>
</table>
</td></tr>
</table>
<p style="margin:0;color:#52525b;font-size:13px;line-height:1.6;">
The student was not detected in {consecutive_misses} consecutive presence scans (60-second intervals).
Please review the situation in the IAMS admin portal.
</p>"""
    return _base_layout(content)


def render_daily_digest(
    faculty_name: str,
    date: str,
    total_sessions: int,
    avg_attendance_rate: float,
    early_leaves: int,
    anomalies: int,
    session_details: list[dict],
) -> str:
    """Render daily digest email for faculty."""
    sessions_html = ""
    for s in session_details[:10]:
        rate_color = "#16a34a" if s.get("rate", 0) >= 75 else "#dc2626"
        sessions_html += f"""
<tr>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:#18181b;font-size:13px;">{s.get('subject_code', '')}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:#18181b;font-size:13px;">{s.get('time', '')}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:{rate_color};font-size:13px;font-weight:600;">{s.get('rate', 0):.0f}%</td>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:#18181b;font-size:13px;">{s.get('present', 0)}/{s.get('enrolled', 0)}</td>
</tr>"""

    rate_color = "#16a34a" if avg_attendance_rate >= 75 else "#dc2626"

    content = f"""
<div style="margin-bottom:24px;">
<span style="display:inline-block;padding:4px 12px;background-color:#eff6ff;color:#2563eb;font-size:12px;font-weight:600;border-radius:9999px;text-transform:uppercase;letter-spacing:0.05em;">Daily Digest</span>
</div>
<p style="margin:0 0 8px;color:#18181b;font-size:16px;line-height:1.5;">
Good evening, {faculty_name}.
</p>
<p style="margin:0 0 24px;color:#52525b;font-size:14px;">
Here's your attendance summary for <strong>{date}</strong>.
</p>
<!-- Stats Row -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
<tr>
<td width="25%" style="padding:12px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:#18181b;font-size:24px;font-weight:700;">{total_sessions}</div>
<div style="color:#71717a;font-size:11px;margin-top:4px;">Sessions</div>
</td>
<td width="4px"></td>
<td width="25%" style="padding:12px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:{rate_color};font-size:24px;font-weight:700;">{avg_attendance_rate:.0f}%</div>
<div style="color:#71717a;font-size:11px;margin-top:4px;">Avg Rate</div>
</td>
<td width="4px"></td>
<td width="25%" style="padding:12px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:#18181b;font-size:24px;font-weight:700;">{early_leaves}</div>
<div style="color:#71717a;font-size:11px;margin-top:4px;">Early Leaves</div>
</td>
<td width="4px"></td>
<td width="25%" style="padding:12px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:#18181b;font-size:24px;font-weight:700;">{anomalies}</div>
<div style="color:#71717a;font-size:11px;margin-top:4px;">Anomalies</div>
</td>
</tr>
</table>
<!-- Session Table -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e4e4e7;border-radius:8px;overflow:hidden;">
<tr style="background-color:#f4f4f5;">
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Subject</th>
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Time</th>
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Rate</th>
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Attendance</th>
</tr>
{sessions_html}
</table>"""
    return _base_layout(content)


def render_weekly_digest(
    student_name: str,
    week_range: str,
    overall_rate: float,
    total_classes: int,
    classes_attended: int,
    subject_breakdown: list[dict],
) -> str:
    """Render weekly digest email for students."""
    subjects_html = ""
    for s in subject_breakdown[:10]:
        rate_color = "#16a34a" if s.get("rate", 0) >= 75 else "#dc2626"
        subjects_html += f"""
<tr>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:#18181b;font-size:13px;">{s.get('subject_code', '')}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:#18181b;font-size:13px;">{s.get('subject_name', '')}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:{rate_color};font-size:13px;font-weight:600;">{s.get('rate', 0):.0f}%</td>
<td style="padding:8px 12px;border-bottom:1px solid #e4e4e7;color:#18181b;font-size:13px;">{s.get('attended', 0)}/{s.get('total', 0)}</td>
</tr>"""

    rate_color = "#16a34a" if overall_rate >= 75 else "#dc2626"
    encouragement = "Great job keeping up!" if overall_rate >= 75 else "Your attendance is below the recommended threshold. Please try to attend more classes."

    content = f"""
<div style="margin-bottom:24px;">
<span style="display:inline-block;padding:4px 12px;background-color:#f0fdf4;color:#16a34a;font-size:12px;font-weight:600;border-radius:9999px;text-transform:uppercase;letter-spacing:0.05em;">Weekly Summary</span>
</div>
<p style="margin:0 0 8px;color:#18181b;font-size:16px;line-height:1.5;">
Hi {student_name},
</p>
<p style="margin:0 0 24px;color:#52525b;font-size:14px;">
Here's your attendance summary for the week of <strong>{week_range}</strong>.
</p>
<!-- Overall Stats -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
<tr>
<td width="33%" style="padding:16px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:{rate_color};font-size:28px;font-weight:700;">{overall_rate:.0f}%</div>
<div style="color:#71717a;font-size:11px;margin-top:4px;">Overall Rate</div>
</td>
<td width="4px"></td>
<td width="33%" style="padding:16px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:#18181b;font-size:28px;font-weight:700;">{classes_attended}/{total_classes}</div>
<div style="color:#71717a;font-size:11px;margin-top:4px;">Classes Attended</div>
</td>
</tr>
</table>
<p style="margin:0 0 24px;color:#52525b;font-size:14px;line-height:1.6;">
{encouragement}
</p>
<!-- Subject Breakdown -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e4e4e7;border-radius:8px;overflow:hidden;">
<tr style="background-color:#f4f4f5;">
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Code</th>
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Subject</th>
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Rate</th>
<th style="padding:8px 12px;text-align:left;color:#71717a;font-size:11px;font-weight:600;text-transform:uppercase;">Attended</th>
</tr>
{subjects_html}
</table>"""
    return _base_layout(content)


def render_low_attendance(
    student_name: str,
    subject_name: str,
    subject_code: str,
    current_rate: float,
    threshold: float,
) -> str:
    """Render low attendance warning email for students."""
    content = f"""
<div style="margin-bottom:24px;">
<span style="display:inline-block;padding:4px 12px;background-color:#fffbeb;color:#d97706;font-size:12px;font-weight:600;border-radius:9999px;text-transform:uppercase;letter-spacing:0.05em;">Low Attendance Warning</span>
</div>
<p style="margin:0 0 8px;color:#18181b;font-size:16px;line-height:1.5;">
Hi {student_name},
</p>
<p style="margin:0 0 24px;color:#52525b;font-size:14px;line-height:1.6;">
Your attendance in <strong>{subject_code} &mdash; {subject_name}</strong> has dropped below the required threshold.
</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
<tr>
<td width="48%" style="padding:20px;text-align:center;background-color:#fef2f2;border-radius:8px;">
<div style="color:#dc2626;font-size:32px;font-weight:700;">{current_rate:.0f}%</div>
<div style="color:#71717a;font-size:12px;margin-top:4px;">Your Current Rate</div>
</td>
<td width="4%"></td>
<td width="48%" style="padding:20px;text-align:center;background-color:#f9fafb;border-radius:8px;">
<div style="color:#18181b;font-size:32px;font-weight:700;">{threshold:.0f}%</div>
<div style="color:#71717a;font-size:12px;margin-top:4px;">Required Threshold</div>
</td>
</tr>
</table>
<p style="margin:0;color:#52525b;font-size:13px;line-height:1.6;">
Please make an effort to attend upcoming classes. If you believe this is an error,
contact your faculty or the registrar's office.
</p>"""
    return _base_layout(content)


def render_broadcast(title: str, message: str) -> str:
    """Render admin broadcast email."""
    content = f"""
<div style="margin-bottom:24px;">
<span style="display:inline-block;padding:4px 12px;background-color:#f0f0f0;color:#18181b;font-size:12px;font-weight:600;border-radius:9999px;text-transform:uppercase;letter-spacing:0.05em;">Announcement</span>
</div>
<h2 style="margin:0 0 16px;color:#18181b;font-size:18px;font-weight:600;">{title}</h2>
<p style="margin:0;color:#374151;font-size:14px;line-height:1.7;white-space:pre-line;">{message}</p>"""
    return _base_layout(content)
