# Faculty History Screen Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the faculty Alerts tab with a History screen featuring class multi-select, date range filtering, session drill-down, and backend-generated PDF export.

**Architecture:** New backend PDF service using ReportLab platypus generates detailed attendance reports. The mobile app adds a History screen with two sub-tabs (Attendance/Alerts), reusing existing alerts composable. Existing attendance APIs are reused for data; one new endpoint serves PDF downloads.

**Tech Stack:** ReportLab (Python PDF), FastAPI StreamingResponse, Kotlin Jetpack Compose, Material 3 DatePicker, OkHttp file download, Android FileProvider.

---

### Task 1: Add `reportlab` dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add reportlab to requirements**

Add at the end of `backend/requirements.txt`:
```
reportlab>=4.0
```

**Step 2: Install and verify**

Run: `docker compose exec api-gateway pip install reportlab`
Then: `docker compose exec api-gateway python -c "from reportlab.platypus import SimpleDocTemplate; print('OK')"`
Expected: `OK`

**Step 3: Rebuild Docker image**

Run: `docker compose build api-gateway`

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add reportlab dependency for PDF generation"
```

---

### Task 2: Create PDF service (`pdf_service.py`)

**Files:**
- Create: `backend/app/services/pdf_service.py`

**Step 1: Write the PDF generation service**

```python
"""PDF report generation using ReportLab platypus."""

import io
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_attendance_pdf(
    faculty_name: str,
    start_date: date,
    end_date: date,
    class_sections: list[dict],
) -> bytes:
    """Generate a detailed attendance PDF report.

    Args:
        faculty_name: Name of the faculty member.
        start_date: Report range start.
        end_date: Report range end.
        class_sections: List of dicts, each with:
            - subject_code: str
            - subject_name: str
            - room_name: str | None
            - summary: dict with total_records, present_count, late_count,
                       absent_count, early_leave_count, attendance_rate
            - records: list of dicts with date, student_name, student_number,
                       status, check_in_time, presence_score

    Returns:
        PDF file content as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=16,
        spaceAfter=6,
    )

    elements: list = []

    # Header
    elements.append(Paragraph("Attendance Report", title_style))
    elements.append(
        Paragraph(
            f"Faculty: {faculty_name} &nbsp;|&nbsp; "
            f"Period: {start_date.isoformat()} to {end_date.isoformat()} &nbsp;|&nbsp; "
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle_style,
        )
    )

    if not class_sections:
        elements.append(Paragraph("No attendance data found for the selected filters.", styles["Normal"]))
        doc.build(elements)
        return buf.getvalue()

    for section in class_sections:
        # Class heading
        room = section.get("room_name") or "—"
        elements.append(
            Paragraph(
                f"{section['subject_code']} — {section['subject_name']} (Room: {room})",
                section_style,
            )
        )

        # Summary table
        s = section["summary"]
        summary_data = [
            ["Total Records", "Present", "Late", "Absent", "Early Leave", "Attendance Rate"],
            [
                str(s.get("total_records", 0)),
                str(s.get("present_count", 0)),
                str(s.get("late_count", 0)),
                str(s.get("absent_count", 0)),
                str(s.get("early_leave_count", 0)),
                f"{s.get('attendance_rate', 0):.1f}%",
            ],
        ]
        summary_table = Table(summary_data, hAlign="LEFT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 8))

        # Detailed records table
        records = section.get("records", [])
        if not records:
            elements.append(Paragraph("No records for this class.", styles["Normal"]))
            continue

        detail_data = [["Date", "Student Name", "Student No.", "Status", "Check-in", "Presence Score"]]
        for r in records:
            detail_data.append(
                [
                    r.get("date", "—"),
                    r.get("student_name", "—"),
                    r.get("student_number", "—"),
                    r.get("status", "—"),
                    r.get("check_in_time", "—") or "—",
                    f"{r['presence_score']:.0f}%" if r.get("presence_score") is not None else "—",
                ]
            )

        col_widths = [80, 160, 90, 70, 70, 80]
        detail_table = Table(detail_data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
        detail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#555555")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
                    ("ALIGN", (3, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(detail_table)

    doc.build(elements)
    return buf.getvalue()
```

**Step 2: Verify import works**

Run: `docker compose exec api-gateway python -c "from app.services.pdf_service import generate_attendance_pdf; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/services/pdf_service.py
git commit -m "feat: add PDF generation service using ReportLab platypus"
```

---

### Task 3: Add `/export/pdf` backend endpoint

**Files:**
- Modify: `backend/app/routers/attendance.py` (add new route near existing `/export` endpoint around line 615)

**Step 1: Add the PDF export endpoint**

Add this import at the top of `attendance.py` with the other imports:
```python
from app.services.pdf_service import generate_attendance_pdf
```

Add this endpoint after the existing `/export` endpoint (after line 761):

```python
@router.get("/export/pdf")
async def export_attendance_pdf(
    schedule_ids: str = Query(..., description="Comma-separated schedule UUIDs, or 'all'"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export detailed attendance report as PDF."""
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse
    import io

    if current_user.role not in ("faculty", "admin"):
        raise HTTPException(status_code=403, detail="Only faculty and admins can export PDF reports")

    try:
        sd = date_type.fromisoformat(start_date)
        ed = date_type.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if sd > ed:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    attendance_repo = AttendanceRepository(db)
    schedule_repo = ScheduleRepository(db)

    # Resolve schedule IDs
    if schedule_ids.strip().lower() == "all":
        if current_user.role == "admin":
            schedules = schedule_repo.get_all()
        else:
            schedules = schedule_repo.get_by_faculty(current_user.id)
    else:
        ids = [s.strip() for s in schedule_ids.split(",") if s.strip()]
        schedules = []
        for sid in ids:
            sched = schedule_repo.get_by_id(sid)
            if sched is None:
                raise HTTPException(status_code=404, detail=f"Schedule {sid} not found")
            if current_user.role == "faculty" and str(sched.faculty_id) != str(current_user.id):
                raise HTTPException(status_code=403, detail=f"Not authorized for schedule {sid}")
            schedules.append(sched)

    if not schedules:
        raise HTTPException(status_code=404, detail="No schedules found")

    # Build class sections
    class_sections = []
    for sched in schedules:
        records = attendance_repo.get_by_schedule(
            schedule_id=str(sched.id),
            start_date=sd,
            end_date=ed,
        )

        summary = attendance_repo.get_schedule_summary(
            schedule_id=str(sched.id),
            start_date=sd,
            end_date=ed,
        )

        record_dicts = []
        for r in records:
            record_dicts.append({
                "date": str(r.date) if hasattr(r, "date") else str(getattr(r, "created_at", "—"))[:10],
                "student_name": getattr(r, "student_name", None) or _get_student_name(db, r.student_id),
                "student_number": getattr(r, "student_number", None) or _get_student_number(db, r.student_id),
                "status": r.status,
                "check_in_time": str(r.check_in_time)[:5] if r.check_in_time else None,
                "presence_score": r.presence_score,
            })

        # Sort by date then student name
        record_dicts.sort(key=lambda x: (x["date"], x["student_name"] or ""))

        class_sections.append({
            "subject_code": sched.subject_code or "—",
            "subject_name": sched.subject_name,
            "room_name": sched.room.name if sched.room else None,
            "summary": {
                "total_records": summary.get("total_records", len(records)),
                "present_count": summary.get("present_count", 0),
                "late_count": summary.get("late_count", 0),
                "absent_count": summary.get("absent_count", 0),
                "early_leave_count": summary.get("early_leave_count", 0),
                "attendance_rate": summary.get("attendance_rate", 0),
            },
            "records": record_dicts,
        })

    faculty_name = f"{current_user.first_name} {current_user.last_name}"
    pdf_bytes = generate_attendance_pdf(
        faculty_name=faculty_name,
        start_date=sd,
        end_date=ed,
        class_sections=class_sections,
    )

    filename = f"attendance_report_{start_date}_to_{end_date}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _get_student_name(db: Session, student_id) -> str:
    """Helper to resolve student name from user ID."""
    from app.models.user import User
    user = db.query(User).filter(User.id == student_id).first()
    if user:
        return f"{user.first_name} {user.last_name}"
    return "Unknown"


def _get_student_number(db: Session, student_id) -> str:
    """Helper to resolve student number from user ID."""
    from app.models.user import User
    user = db.query(User).filter(User.id == student_id).first()
    return getattr(user, "student_number", "—") or "—" if user else "—"
```

**Step 2: Verify endpoint loads**

Run: `docker compose restart api-gateway && sleep 3 && docker compose exec api-gateway curl -s http://localhost:8000/docs | grep -c "export/pdf"`
Expected: At least `1`

Note: This endpoint may need adjustment based on the exact repository method signatures. Read `backend/app/repositories/attendance_repository.py` and `backend/app/repositories/schedule_repository.py` to verify method names (`get_by_schedule`, `get_schedule_summary`, `get_by_faculty`, `get_all`, `get_by_id`). Adapt the endpoint code to match actual method signatures.

**Step 3: Commit**

```bash
git add backend/app/routers/attendance.py
git commit -m "feat: add /export/pdf endpoint for attendance PDF reports"
```

---

### Task 4: Add `FACULTY_HISTORY` route constant (Android)

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/navigation/Routes.kt` (line ~51)

**Step 1: Add route constant**

Replace:
```kotlin
const val FACULTY_ALERTS = "faculty/alerts"
```
With:
```kotlin
const val FACULTY_ALERTS = "faculty/alerts"
const val FACULTY_HISTORY = "faculty/history"
```

**Step 2: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/navigation/Routes.kt
git commit -m "feat: add FACULTY_HISTORY route constant"
```

---

### Task 5: Add `exportAttendancePdf()` to ApiService (Android)

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/data/api/ApiService.kt`
- Modify: `android/app/src/main/java/com/iams/app/data/model/Models.kt`

**Step 1: Add the API method to ApiService**

Add after the existing attendance methods (around line 91):

```kotlin
@GET("attendance/export/pdf")
@Streaming
suspend fun exportAttendancePdf(
    @Query("schedule_ids") scheduleIds: String,
    @Query("start_date") startDate: String,
    @Query("end_date") endDate: String,
): Response<ResponseBody>
```

Make sure `okhttp3.ResponseBody` is imported at the top.

**Step 2: Add `getAttendanceRecords()` method if not present**

Check if a general attendance list endpoint exists. If not, add:

```kotlin
@GET("attendance")
suspend fun getAttendanceRecords(
    @Query("schedule_id") scheduleId: String? = null,
    @Query("start_date") startDate: String? = null,
    @Query("end_date") endDate: String? = null,
    @Query("limit") limit: Int? = null,
): Response<List<AttendanceRecordResponse>>
```

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/data/api/ApiService.kt
git commit -m "feat: add exportAttendancePdf and getAttendanceRecords API methods"
```

---

### Task 6: Create `FacultyHistoryViewModel.kt`

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHistoryViewModel.kt`

**Step 1: Write the ViewModel**

```kotlin
package com.iams.app.ui.faculty

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.AttendanceSummaryResponse
import com.iams.app.data.model.ScheduleResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

data class SessionSummary(
    val date: String,
    val scheduleId: String,
    val subjectCode: String?,
    val subjectName: String,
    val presentCount: Int = 0,
    val lateCount: Int = 0,
    val absentCount: Int = 0,
    val earlyLeaveCount: Int = 0,
    val records: List<AttendanceRecordResponse> = emptyList(),
)

data class FacultyHistoryUiState(
    val isLoading: Boolean = false,
    val isExporting: Boolean = false,
    val error: String? = null,
    val schedules: List<ScheduleResponse> = emptyList(),
    val selectedScheduleIds: Set<String> = emptySet(),
    val selectAll: Boolean = true,
    val startDate: LocalDate = LocalDate.now().withDayOfMonth(1),
    val endDate: LocalDate = LocalDate.now(),
    val sessions: List<SessionSummary> = emptyList(),
    val overallSummary: AttendanceSummaryResponse? = null,
    val hasLoaded: Boolean = false,
    val exportSuccess: Boolean = false,
)

@HiltViewModel
class FacultyHistoryViewModel @Inject constructor(
    private val apiService: ApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyHistoryUiState())
    val uiState: StateFlow<FacultyHistoryUiState> = _uiState.asStateFlow()

    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    init {
        loadSchedules()
    }

    private fun loadSchedules() {
        viewModelScope.launch {
            try {
                val response = apiService.getMySchedules()
                if (response.isSuccessful) {
                    val schedules = response.body() ?: emptyList()
                    _uiState.update {
                        it.copy(
                            schedules = schedules,
                            selectedScheduleIds = schedules.map { s -> s.id }.toSet(),
                            selectAll = true,
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = "Failed to load schedules: ${e.message}") }
            }
        }
    }

    fun toggleScheduleSelection(scheduleId: String) {
        _uiState.update { state ->
            val newSet = state.selectedScheduleIds.toMutableSet()
            if (newSet.contains(scheduleId)) newSet.remove(scheduleId) else newSet.add(scheduleId)
            state.copy(
                selectedScheduleIds = newSet,
                selectAll = newSet.size == state.schedules.size,
            )
        }
    }

    fun toggleSelectAll() {
        _uiState.update { state ->
            if (state.selectAll) {
                state.copy(selectedScheduleIds = emptySet(), selectAll = false)
            } else {
                state.copy(
                    selectedScheduleIds = state.schedules.map { it.id }.toSet(),
                    selectAll = true,
                )
            }
        }
    }

    fun setStartDate(date: LocalDate) {
        _uiState.update { it.copy(startDate = date) }
    }

    fun setEndDate(date: LocalDate) {
        _uiState.update { it.copy(endDate = date) }
    }

    fun loadHistory() {
        val state = _uiState.value
        if (state.selectedScheduleIds.isEmpty()) {
            _uiState.update { it.copy(error = "Please select at least one class") }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            try {
                val start = state.startDate.format(dateFormatter)
                val end = state.endDate.format(dateFormatter)

                // Fetch attendance records for each selected schedule in parallel
                val recordDeferreds = state.selectedScheduleIds.map { scheduleId ->
                    async {
                        val resp = apiService.getAttendanceRecords(
                            scheduleId = scheduleId,
                            startDate = start,
                            endDate = end,
                        )
                        if (resp.isSuccessful) {
                            val schedule = state.schedules.find { it.id == scheduleId }
                            Triple(scheduleId, schedule, resp.body() ?: emptyList())
                        } else null
                    }
                }

                // Fetch summaries in parallel
                val summaryDeferreds = state.selectedScheduleIds.map { scheduleId ->
                    async {
                        val resp = apiService.getScheduleAttendanceSummary(
                            scheduleId = scheduleId,
                            startDate = start,
                            endDate = end,
                        )
                        if (resp.isSuccessful) scheduleId to resp.body() else null
                    }
                }

                val recordResults = recordDeferreds.awaitAll().filterNotNull()
                val summaryResults = summaryDeferreds.awaitAll().filterNotNull().toMap()

                // Group records into sessions (by date + schedule)
                val sessions = mutableListOf<SessionSummary>()
                for ((scheduleId, schedule, records) in recordResults) {
                    val byDate = records.groupBy { it.date }
                    for ((date, dateRecords) in byDate) {
                        sessions.add(
                            SessionSummary(
                                date = date,
                                scheduleId = scheduleId,
                                subjectCode = schedule?.subjectCode,
                                subjectName = schedule?.subjectName ?: "Unknown",
                                presentCount = dateRecords.count { it.status.equals("present", true) },
                                lateCount = dateRecords.count { it.status.equals("late", true) },
                                absentCount = dateRecords.count { it.status.equals("absent", true) },
                                earlyLeaveCount = dateRecords.count { it.status.equals("early_leave", true) },
                                records = dateRecords,
                            )
                        )
                    }
                }

                sessions.sortByDescending { it.date }

                // Aggregate overall summary
                val totalPresent = summaryResults.values.sumOf { it?.presentCount ?: 0 }
                val totalLate = summaryResults.values.sumOf { it?.lateCount ?: 0 }
                val totalAbsent = summaryResults.values.sumOf { it?.absentCount ?: 0 }
                val totalClasses = summaryResults.values.sumOf { it?.totalClasses ?: 0 }
                val overallRate = if (totalClasses > 0) {
                    (totalPresent + totalLate).toFloat() / totalClasses * 100
                } else 0f

                _uiState.update {
                    it.copy(
                        isLoading = false,
                        sessions = sessions,
                        hasLoaded = true,
                        overallSummary = AttendanceSummaryResponse(
                            totalClasses = totalClasses,
                            presentCount = totalPresent,
                            lateCount = totalLate,
                            absentCount = totalAbsent,
                            attendanceRate = overallRate,
                        ),
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(isLoading = false, error = "Failed to load history: ${e.message}") }
            }
        }
    }

    fun exportPdf(context: Context) {
        val state = _uiState.value
        viewModelScope.launch {
            _uiState.update { it.copy(isExporting = true, exportSuccess = false) }

            try {
                val scheduleIdsParam = if (state.selectAll) "all"
                    else state.selectedScheduleIds.joinToString(",")
                val start = state.startDate.format(dateFormatter)
                val end = state.endDate.format(dateFormatter)

                val response = apiService.exportAttendancePdf(
                    scheduleIds = scheduleIdsParam,
                    startDate = start,
                    endDate = end,
                )

                if (response.isSuccessful) {
                    val body = response.body()
                    if (body != null) {
                        val filename = "attendance_report_${start}_to_${end}.pdf"
                        val file = File(context.cacheDir, filename)
                        file.outputStream().use { out ->
                            body.byteStream().copyTo(out)
                        }

                        val uri = FileProvider.getUriForFile(
                            context,
                            "${context.packageName}.fileprovider",
                            file,
                        )

                        val intent = Intent(Intent.ACTION_VIEW).apply {
                            setDataAndType(uri, "application/pdf")
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        context.startActivity(intent)
                        _uiState.update { it.copy(isExporting = false, exportSuccess = true) }
                    } else {
                        _uiState.update { it.copy(isExporting = false, error = "Empty response") }
                    }
                } else {
                    _uiState.update { it.copy(isExporting = false, error = "Export failed: ${response.code()}") }
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(isExporting = false, error = "Export failed: ${e.message}") }
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    fun clearExportSuccess() {
        _uiState.update { it.copy(exportSuccess = false) }
    }
}
```

**Step 2: Verify compilation**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL (or type errors to fix — adapt to actual ApiService method names)

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyHistoryViewModel.kt
git commit -m "feat: add FacultyHistoryViewModel with class filter, date range, and PDF export"
```

---

### Task 7: Create `FacultyHistoryScreen.kt`

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHistoryScreen.kt`

**Step 1: Write the History screen composable**

This is the largest file. It contains:
- Two-tab layout (Attendance | Alerts)
- Class multi-select with chips
- Date range pickers (Material 3 DatePickerDialog)
- Summary card
- Session cards in LazyColumn
- Expandable session → student detail rows
- Export PDF button
- Reuses `FacultyAlertsScreen` content for Alerts tab

```kotlin
package com.iams.app.ui.faculty

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSHeader
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyHistoryScreen(
    navController: NavController,
    viewModel: FacultyHistoryViewModel = hiltViewModel(),
    alertsViewModel: FacultyAlertsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Attendance", "Alerts")

    val snackbarHostState = remember { SnackbarHostState() }

    // Show errors via snackbar
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    LaunchedEffect(uiState.exportSuccess) {
        if (uiState.exportSuccess) {
            snackbarHostState.showSnackbar("PDF exported successfully")
            viewModel.clearExportSuccess()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            IAMSHeader(
                title = "History",
                navController = navController,
            )

            // Tab row
            TabRow(
                selectedTabIndex = selectedTab,
                containerColor = MaterialTheme.colorScheme.surface,
            ) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = {
                            Text(
                                title,
                                fontWeight = if (selectedTab == index) FontWeight.Bold else FontWeight.Normal,
                            )
                        },
                    )
                }
            }

            when (selectedTab) {
                0 -> AttendanceHistoryTab(
                    uiState = uiState,
                    onToggleSchedule = viewModel::toggleScheduleSelection,
                    onToggleSelectAll = viewModel::toggleSelectAll,
                    onSetStartDate = viewModel::setStartDate,
                    onSetEndDate = viewModel::setEndDate,
                    onApply = viewModel::loadHistory,
                    onExportPdf = { viewModel.exportPdf(context) },
                )
                1 -> FacultyAlertsContent(
                    navController = navController,
                    viewModel = alertsViewModel,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AttendanceHistoryTab(
    uiState: FacultyHistoryUiState,
    onToggleSchedule: (String) -> Unit,
    onToggleSelectAll: () -> Unit,
    onSetStartDate: (LocalDate) -> Unit,
    onSetEndDate: (LocalDate) -> Unit,
    onApply: () -> Unit,
    onExportPdf: () -> Unit,
) {
    var showClassSelector by remember { mutableStateOf(false) }
    var showStartPicker by remember { mutableStateOf(false) }
    var showEndPicker by remember { mutableStateOf(false) }
    val dateFormatter = remember { DateTimeFormatter.ofPattern("MMM d, yyyy") }

    Box(modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 80.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Filters
            item {
                // Class selector
                OutlinedCard(
                    onClick = { showClassSelector = !showClassSelector },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Classes", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(
                                when {
                                    uiState.selectAll -> "All Classes"
                                    uiState.selectedScheduleIds.isEmpty() -> "None selected"
                                    uiState.selectedScheduleIds.size == 1 -> {
                                        uiState.schedules.find { it.id == uiState.selectedScheduleIds.first() }?.subjectName ?: "1 class"
                                    }
                                    else -> "${uiState.selectedScheduleIds.size} classes selected"
                                },
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                        Icon(Icons.Default.FilterList, contentDescription = "Select classes")
                    }
                }

                AnimatedVisibility(visible = showClassSelector) {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 4.dp),
                    ) {
                        Column(modifier = Modifier.padding(8.dp)) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onToggleSelectAll() }
                                    .padding(vertical = 8.dp, horizontal = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Checkbox(checked = uiState.selectAll, onCheckedChange = { onToggleSelectAll() })
                                Spacer(Modifier.width(8.dp))
                                Text("All Classes", fontWeight = FontWeight.Medium)
                            }
                            HorizontalDivider()
                            uiState.schedules.forEach { schedule ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { onToggleSchedule(schedule.id) }
                                        .padding(vertical = 6.dp, horizontal = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Checkbox(
                                        checked = uiState.selectedScheduleIds.contains(schedule.id),
                                        onCheckedChange = { onToggleSchedule(schedule.id) },
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Column {
                                        Text(schedule.subjectName, style = MaterialTheme.typography.bodyMedium)
                                        if (schedule.subjectCode != null) {
                                            Text(
                                                schedule.subjectCode,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Date range
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedCard(
                        onClick = { showStartPicker = true },
                        modifier = Modifier.weight(1f),
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(Icons.Default.CalendarMonth, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Column {
                                Text("From", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(uiState.startDate.format(dateFormatter), style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                    OutlinedCard(
                        onClick = { showEndPicker = true },
                        modifier = Modifier.weight(1f),
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(Icons.Default.CalendarMonth, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Column {
                                Text("To", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(uiState.endDate.format(dateFormatter), style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }

            // Apply button
            item {
                Button(
                    onClick = onApply,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !uiState.isLoading && uiState.selectedScheduleIds.isNotEmpty(),
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(if (uiState.isLoading) "Loading..." else "Apply Filters")
                }
            }

            // Summary card
            if (uiState.hasLoaded && uiState.overallSummary != null) {
                item {
                    val summary = uiState.overallSummary
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Overview", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceEvenly,
                            ) {
                                StatItem("Sessions", "${summary.totalClasses}")
                                StatItem("Present", "${summary.presentCount}")
                                StatItem("Late", "${summary.lateCount}")
                                StatItem("Absent", "${summary.absentCount}")
                                StatItem("Rate", String.format("%.0f%%", summary.attendanceRate))
                            }
                        }
                    }
                }
            }

            // Session cards
            if (uiState.hasLoaded) {
                if (uiState.sessions.isEmpty()) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 32.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text("No attendance records found", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                } else {
                    items(uiState.sessions, key = { "${it.date}_${it.scheduleId}" }) { session ->
                        SessionCard(session = session)
                    }
                }
            }
        }

        // Export PDF button
        if (uiState.hasLoaded && uiState.sessions.isNotEmpty()) {
            Button(
                onClick = onExportPdf,
                enabled = !uiState.isExporting,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(16.dp),
            ) {
                if (uiState.isExporting) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                    Spacer(Modifier.width(8.dp))
                }
                Icon(Icons.Default.PictureAsPdf, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(if (uiState.isExporting) "Exporting..." else "Export PDF")
            }
        }
    }

    // Date pickers
    if (showStartPicker) {
        val datePickerState = rememberDatePickerState(
            initialSelectedDateMillis = uiState.startDate.atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showStartPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    datePickerState.selectedDateMillis?.let { millis ->
                        onSetStartDate(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()).toLocalDate())
                    }
                    showStartPicker = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { showStartPicker = false }) { Text("Cancel") } },
        ) { DatePicker(state = datePickerState) }
    }
    if (showEndPicker) {
        val datePickerState = rememberDatePickerState(
            initialSelectedDateMillis = uiState.endDate.atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showEndPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    datePickerState.selectedDateMillis?.let { millis ->
                        onSetEndDate(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()).toLocalDate())
                    }
                    showEndPicker = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { showEndPicker = false }) { Text("Cancel") } },
        ) { DatePicker(state = datePickerState) }
    }
}

@Composable
private fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SessionCard(session: SessionSummary) {
    var expanded by remember { mutableStateOf(false) }
    val total = session.presentCount + session.lateCount + session.absentCount + session.earlyLeaveCount
    val rate = if (total > 0) (session.presentCount + session.lateCount).toFloat() / total * 100 else 0f

    Card(
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier
                .clickable { expanded = !expanded }
                .padding(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        session.subjectCode?.let { "$it — ${session.subjectName}" } ?: session.subjectName,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(session.date, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(String.format("%.0f%%", rate), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(4.dp))
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = if (expanded) "Collapse" else "Expand",
                )
            }

            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                StatusChip("P:${session.presentCount}", MaterialTheme.colorScheme.primary)
                StatusChip("L:${session.lateCount}", MaterialTheme.colorScheme.tertiary)
                StatusChip("A:${session.absentCount}", MaterialTheme.colorScheme.error)
                if (session.earlyLeaveCount > 0) {
                    StatusChip("EL:${session.earlyLeaveCount}", MaterialTheme.colorScheme.error)
                }
            }

            // Expanded student records
            AnimatedVisibility(visible = expanded) {
                Column(modifier = Modifier.padding(top = 8.dp)) {
                    HorizontalDivider(modifier = Modifier.padding(bottom = 8.dp))
                    session.records.sortedBy { it.studentName }.forEach { record ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 3.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                record.studentName ?: "Unknown",
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                record.status.replaceFirstChar { it.uppercase() },
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Medium,
                                color = when (record.status.lowercase()) {
                                    "present" -> MaterialTheme.colorScheme.primary
                                    "late" -> MaterialTheme.colorScheme.tertiary
                                    "absent" -> MaterialTheme.colorScheme.error
                                    else -> MaterialTheme.colorScheme.onSurface
                                },
                            )
                            record.presenceScore?.let {
                                Text(
                                    String.format("%.0f%%", it),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(start = 8.dp),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusChip(text: String, color: androidx.compose.ui.graphics.Color) {
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = color,
        fontWeight = FontWeight.Medium,
        modifier = Modifier
            .background(color.copy(alpha = 0.1f), RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp),
    )
}
```

**Step 2: Verify compilation**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyHistoryScreen.kt
git commit -m "feat: add FacultyHistoryScreen with attendance/alerts tabs, filters, and PDF export"
```

---

### Task 8: Extract `FacultyAlertsContent` composable

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyAlertsScreen.kt`

The History screen's Alerts tab needs to render the alerts UI without its own `Scaffold`/header. Extract the inner content into a `FacultyAlertsContent` composable.

**Step 1: Add a new public composable**

At the bottom of `FacultyAlertsScreen.kt`, add a `FacultyAlertsContent` composable that contains the filter bar + alerts list (the body of the current screen minus the `IAMSHeader` and `Scaffold`). It should accept `navController` and `viewModel` as params.

Look at the existing `FacultyAlertsScreen` composable body (lines ~67-150). The new `FacultyAlertsContent` should contain everything after the `IAMSHeader` — the filter bar, pull-to-refresh, alerts list, loading/error/empty states.

```kotlin
@Composable
fun FacultyAlertsContent(
    navController: NavController,
    viewModel: FacultyAlertsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    // ... same body as FacultyAlertsScreen but without IAMSHeader/Scaffold wrapper
}
```

**Step 2: Verify compilation**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyAlertsScreen.kt
git commit -m "refactor: extract FacultyAlertsContent composable for reuse in History screen"
```

---

### Task 9: Wire up navigation — replace Alerts tab with History

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/navigation/IAMSNavHost.kt`

**Step 1: Update faculty tabs list (line ~99)**

Change the Alerts tab entry:
```kotlin
// Before:
BottomNavTab("Alerts", Icons.Outlined.ReportProblem, Icons.Filled.ReportProblem, Routes.FACULTY_ALERTS),

// After:
BottomNavTab("History", Icons.Outlined.Assignment, Icons.Filled.Assignment, Routes.FACULTY_HISTORY),
```

Add imports for `Icons.Outlined.Assignment` and `Icons.Filled.Assignment`.

**Step 2: Add History composable route (near line ~287)**

Add this composable alongside the existing faculty routes:

```kotlin
composable(Routes.FACULTY_HISTORY) {
    FacultyHistoryScreen(navController = navController)
}
```

Add import: `com.iams.app.ui.faculty.FacultyHistoryScreen`

Keep the existing `composable(Routes.FACULTY_ALERTS)` route — it's still a valid deep-link target even though it's not a tab anymore.

**Step 3: Verify compilation**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

**Step 4: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/navigation/IAMSNavHost.kt
git commit -m "feat: replace Alerts tab with History in faculty bottom navigation"
```

---

### Task 10: Verify FileProvider configuration

**Files:**
- Check: `android/app/src/main/AndroidManifest.xml`
- Check: `android/app/src/main/res/xml/file_paths.xml` (may not exist)

**Step 1: Verify FileProvider is declared in AndroidManifest.xml**

Search for `FileProvider` in the manifest. If it doesn't exist, add inside `<application>`:

```xml
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>
```

**Step 2: Create/verify `file_paths.xml`**

At `android/app/src/main/res/xml/file_paths.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<paths>
    <cache-path name="cache" path="." />
</paths>
```

**Step 3: Verify build**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

**Step 4: Commit (only if changes were needed)**

```bash
git add android/app/src/main/AndroidManifest.xml android/app/src/main/res/xml/file_paths.xml
git commit -m "chore: configure FileProvider for PDF sharing"
```

---

### Task 11: Integration testing — backend PDF endpoint

**Step 1: Start the stack**

Run: `docker compose up -d`

**Step 2: Seed data**

Run: `docker compose exec -T api-gateway python -m scripts.seed_data`

**Step 3: Get a faculty token**

```bash
TOKEN=$(docker compose exec -T api-gateway python -c "
import httpx, json
r = httpx.post('http://localhost:8000/api/v1/auth/login', json={'email': 'faculty.eb226@gmail.com', 'password': 'password123'})
print(json.loads(r.text)['access_token'])
")
echo $TOKEN
```

**Step 4: Test the PDF endpoint**

```bash
curl -s -o /tmp/test_report.pdf \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/attendance/export/pdf?schedule_ids=all&start_date=2026-01-01&end_date=2026-04-04"

file /tmp/test_report.pdf
# Expected: /tmp/test_report.pdf: PDF document
```

**Step 5: Open and visually verify the PDF**

Run: `open /tmp/test_report.pdf` (macOS)

Verify it contains:
- Header with faculty name, date range, generation timestamp
- Per-class sections with summary tables
- Detailed student-by-student rows

**Step 6: Fix any issues found, then commit fixes if needed**

---

### Task 12: Build and test Android app

**Step 1: Full build**

Run: `cd android && ./gradlew assembleDebug 2>&1 | tail -10`
Expected: BUILD SUCCESSFUL

**Step 2: Install on device/emulator**

Run: `cd android && ./gradlew installDebug`

**Step 3: Manual testing checklist**

- [ ] History tab appears in bottom nav (4th position, Assignment icon)
- [ ] Attendance sub-tab is default
- [ ] Alerts sub-tab shows existing alerts
- [ ] Class selector shows all faculty's classes
- [ ] "All Classes" toggle works
- [ ] Date range pickers open and set dates
- [ ] Apply button fetches and displays session cards
- [ ] Tapping a session card expands student details
- [ ] Export PDF button downloads and opens PDF
- [ ] PDF contains correct data matching the filters

**Step 4: Final commit if any fixes needed**

---

## Lessons

- The existing `/export` endpoint (CSV/JSON) at line 615 of `attendance.py` is a good reference pattern for the PDF endpoint — same auth checks, schedule resolution, and date range handling.
- `AttendanceRepository` method signatures must be verified before writing the endpoint — the plan assumes `get_by_schedule()` and `get_schedule_summary()` exist with those exact names.
- FileProvider configuration is easy to forget — always verify it exists before assuming file sharing will work on Android.
- ReportLab's `platypus` layout engine handles page breaks automatically, which matters for large date ranges with many sessions.
