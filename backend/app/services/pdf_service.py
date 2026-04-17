"""
PDF Service

Generates attendance report PDFs using ReportLab platypus.
"""

import io
from datetime import date, datetime, timedelta, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Philippine Time (UTC+8)
PHT = timezone(timedelta(hours=8))


def generate_attendance_pdf(
    faculty_name: str,
    start_date: date,
    end_date: date,
    class_sections: list[dict],
) -> bytes:
    """
    Generate a detailed attendance report PDF.

    Args:
        faculty_name: Name of the faculty member
        start_date: Report start date
        end_date: Report end date
        class_sections: List of dicts, each containing:
            - subject_code, subject_name, room_name
            - summary: dict with total_records, present_count, late_count,
              absent_count, early_leave_count, attendance_rate
            - records: list of dicts with date, student_name, student_number,
              status, check_in_time, presence_score

    Returns:
        PDF file as bytes
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        spaceAfter=2,
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=14,
        spaceAfter=4,
        textColor=colors.HexColor("#1a1a1a"),
    )
    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
    )
    cell_style_white = ParagraphStyle(
        "CellStyleWhite",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.white,
    )

    elements: list = []

    # --- Header ---
    now_pht = datetime.now(PHT)
    elements.append(Paragraph("Attendance Report", title_style))
    elements.append(Paragraph(f"Faculty: {faculty_name}", subtitle_style))
    elements.append(
        Paragraph(
            f"Period: {start_date.strftime('%B %d, %Y')} — {end_date.strftime('%B %d, %Y')}",
            subtitle_style,
        )
    )
    elements.append(
        Paragraph(
            f"Generated: {now_pht.strftime('%B %d, %Y at %I:%M %p')} (PHT)",
            subtitle_style,
        )
    )
    elements.append(Spacer(1, 10))

    # Filter to only classes that have records
    sections_with_data = [s for s in class_sections if s.get("records")]

    if not sections_with_data:
        elements.append(Paragraph("No attendance records found for the selected period.", styles["Normal"]))
    else:
        for section in sections_with_data:
            subject_code = section.get("subject_code", "N/A")
            subject_name = section.get("subject_name", "N/A")
            room_name = section.get("room_name", "N/A")
            summary = section.get("summary", {})
            records = section.get("records", [])

            # --- Section title ---
            elements.append(
                Paragraph(
                    f"{subject_code} — {subject_name} (Room: {room_name})",
                    section_title_style,
                )
            )

            # --- Summary table ---
            summary_data = [
                ["Total Records", "Present", "Late", "Absent", "Early Leave", "Rate"],
                [
                    str(summary.get("total_records", 0)),
                    str(summary.get("present_count", 0)),
                    str(summary.get("late_count", 0)),
                    str(summary.get("absent_count", 0)),
                    str(summary.get("early_leave_count", 0)),
                    f"{summary.get('attendance_rate', 0.0):.1f}%",
                ],
            ]

            summary_table = Table(summary_data, hAlign="LEFT")
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("FONTSIZE", (0, 1), (-1, 1), 8),
                        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ecf0f1")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(summary_table)
            elements.append(Spacer(1, 6))

            # --- Detailed records table ---
            sorted_records = sorted(records, key=lambda r: (r.get("date", ""), r.get("student_name", "")))

            # A4 portrait width minus margins
            available_width = A4[0] - 30 * mm
            col_widths = [
                available_width * 0.14,  # Date
                available_width * 0.28,  # Student Name
                available_width * 0.15,  # Student No.
                available_width * 0.13,  # Status
                available_width * 0.15,  # Check-in
                available_width * 0.15,  # Presence Score
            ]

            header_row = [
                Paragraph("<b>Date</b>", cell_style_white),
                Paragraph("<b>Student Name</b>", cell_style_white),
                Paragraph("<b>Student No.</b>", cell_style_white),
                Paragraph("<b>Status</b>", cell_style_white),
                Paragraph("<b>Check-in</b>", cell_style_white),
                Paragraph("<b>Presence Score</b>", cell_style_white),
            ]
            table_data = [header_row]

            for rec in sorted_records:
                rec_date = rec.get("date", "")
                if isinstance(rec_date, date):
                    rec_date = rec_date.strftime("%Y-%m-%d")

                check_in = rec.get("check_in_time", "")
                if isinstance(check_in, datetime):
                    check_in = check_in.strftime("%I:%M:%S %p")
                elif check_in is None:
                    check_in = "—"

                presence = rec.get("presence_score", 0)
                if presence is None:
                    presence = 0
                presence_str = f"{presence:.1f}%"

                status_val = rec.get("status", "unknown")
                if hasattr(status_val, "value"):
                    status_val = status_val.value
                status_display = str(status_val).replace("_", " ").title()

                table_data.append(
                    [
                        Paragraph(str(rec_date), cell_style),
                        Paragraph(str(rec.get("student_name", "Unknown")), cell_style),
                        Paragraph(str(rec.get("student_number", "N/A")), cell_style),
                        Paragraph(status_display, cell_style),
                        Paragraph(str(check_in), cell_style),
                        Paragraph(presence_str, cell_style),
                    ]
                )

            records_table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")

            style_cmds = [
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]

            # Alternating row colors
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f6fa")))
                else:
                    style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.white))

            records_table.setStyle(TableStyle(style_cmds))
            elements.append(records_table)
            elements.append(Spacer(1, 10))

    # Build PDF with page numbers
    def _add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(
            A4[0] / 2,
            0.3 * inch,
            f"Page {page_num}",
        )
        canvas.restoreState()

    doc.build(elements, onFirstPage=_add_page_number, onLaterPages=_add_page_number)

    return buf.getvalue()


def generate_alerts_pdf(
    faculty_name: str,
    filter_label: str,
    alerts: list[dict],
) -> bytes:
    """
    Generate an early leave alerts report PDF.

    Args:
        faculty_name: Name of the faculty member
        filter_label: Filter description (e.g. "Today", "This Week", "All")
        alerts: List of dicts, each containing:
            - student_name, student_student_id, subject_code, subject_name
            - detected_at, returned, returned_at, absence_duration_seconds, date

    Returns:
        PDF file as bytes
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "AlertsTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "AlertsSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        spaceAfter=2,
    )
    cell_style = ParagraphStyle(
        "AlertsCellStyle",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
    )
    cell_style_white = ParagraphStyle(
        "AlertsCellStyleWhite",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.white,
    )

    elements: list = []

    # --- Header ---
    now_pht = datetime.now(PHT)
    elements.append(Paragraph("Early Leave Alerts Report", title_style))
    elements.append(Paragraph(f"Faculty: {faculty_name}", subtitle_style))
    elements.append(Paragraph(f"Filter: {filter_label}", subtitle_style))
    elements.append(
        Paragraph(
            f"Generated: {now_pht.strftime('%B %d, %Y at %I:%M %p')} (PHT)",
            subtitle_style,
        )
    )
    elements.append(Spacer(1, 10))

    if not alerts:
        elements.append(Paragraph("No early leave alerts found for the selected filter.", styles["Normal"]))
    else:
        # --- Summary table ---
        total = len(alerts)
        still_absent = sum(1 for a in alerts if not a.get("returned"))
        returned = sum(1 for a in alerts if a.get("returned"))

        summary_data = [
            ["Total Alerts", "Still Absent", "Returned"],
            [str(total), str(still_absent), str(returned)],
        ]
        summary_table = Table(summary_data, hAlign="LEFT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("FONTSIZE", (0, 1), (-1, 1), 8),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ecf0f1")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 10))

        # --- Detail table ---
        available_width = A4[0] - 30 * mm
        col_widths = [
            available_width * 0.12,  # Date
            available_width * 0.22,  # Student Name
            available_width * 0.13,  # Student No.
            available_width * 0.17,  # Subject
            available_width * 0.13,  # Detected At
            available_width * 0.12,  # Duration
            available_width * 0.11,  # Status
        ]

        header_row = [
            Paragraph("<b>Date</b>", cell_style_white),
            Paragraph("<b>Student Name</b>", cell_style_white),
            Paragraph("<b>Student No.</b>", cell_style_white),
            Paragraph("<b>Subject</b>", cell_style_white),
            Paragraph("<b>Detected At</b>", cell_style_white),
            Paragraph("<b>Duration</b>", cell_style_white),
            Paragraph("<b>Status</b>", cell_style_white),
        ]
        table_data = [header_row]

        # Sort: still-absent first, then by detected_at descending
        sorted_alerts = sorted(
            alerts,
            key=lambda a: (a.get("returned", False), -(a.get("detected_at_ts", 0))),
        )

        for alert in sorted_alerts:
            alert_date = alert.get("date", "")
            if isinstance(alert_date, date):
                alert_date = alert_date.strftime("%Y-%m-%d")

            detected_at = alert.get("detected_at", "")
            if isinstance(detected_at, datetime):
                detected_at = detected_at.strftime("%I:%M %p")
            elif detected_at is None:
                detected_at = "—"

            duration_seconds = alert.get("absence_duration_seconds")
            if duration_seconds and duration_seconds > 0:
                mins = duration_seconds // 60
                secs = duration_seconds % 60
                duration_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            else:
                duration_str = "—"

            status_str = "Returned" if alert.get("returned") else "Still Absent"

            table_data.append(
                [
                    Paragraph(str(alert_date), cell_style),
                    Paragraph(str(alert.get("student_name", "Unknown")), cell_style),
                    Paragraph(str(alert.get("student_student_id", "N/A")), cell_style),
                    Paragraph(str(alert.get("subject_code", "N/A")), cell_style),
                    Paragraph(str(detected_at), cell_style),
                    Paragraph(duration_str, cell_style),
                    Paragraph(status_str, cell_style),
                ]
            )

        records_table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")

        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f6fa")))
            else:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.white))

        records_table.setStyle(TableStyle(style_cmds))
        elements.append(records_table)

    def _add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(A4[0] / 2, 0.3 * inch, f"Page {page_num}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=_add_page_number, onLaterPages=_add_page_number)

    return buf.getvalue()
