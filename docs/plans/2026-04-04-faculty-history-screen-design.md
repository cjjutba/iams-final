# Faculty History Screen — Design Doc

**Date:** 2026-04-04
**Status:** Approved
**Approach:** ReportLab platypus for backend PDF generation

## Summary

Replace the Alerts tab in the faculty bottom navigation with a History screen. The History screen has two sub-tabs: **Attendance** (default) and **Alerts**. The Attendance tab allows faculty to select one or more classes, pick a date range, view session-by-session attendance data with drill-down to student-level detail, and export a detailed PDF report. The Alerts sub-tab preserves existing alert functionality as-is.

## Requirements

1. Replace Alerts bottom nav tab with History
2. Class selector: single, multi, or all classes
3. Date range filter (start date, end date), defaults to current month
4. Per-session summary view (date, subject, present/late/absent/early-leave counts)
5. Drill-down into student-by-student breakdown per session
6. Export detailed PDF report via backend endpoint
7. Alerts functionality preserved as sub-tab within History

## Screen Layout & Navigation

### Bottom Bar Change

- **4th tab:** `Alerts` (ReportProblem icon) → `History` (Assignment icon)
- Route: `FACULTY_HISTORY`

### History Screen Structure

```
┌──────────────────────────────┐
│ IAMSHeader: "History" + 🔔   │
├──────────────────────────────┤
│  [ Attendance ]  [ Alerts ]  │  ← Toggle tabs
├──────────────────────────────┤
│ Class Selector (multi-select)│  ← Dropdown/bottom-sheet with chips
│ Date Range: [Start] - [End]  │  ← Material 3 DatePickerDialog
│         [ Apply ]            │
├──────────────────────────────┤
│ Summary Card                 │  ← Total Sessions, Present, Late,
│ (aggregated stats)           │     Absent, Early Leave, Rate %
├──────────────────────────────┤
│ Session Cards (LazyColumn)   │
│ ┌──────────────────────────┐ │
│ │ Apr 2 - Math 101         │ │
│ │ P:18  L:2  A:5  EL:0    │ │
│ │ Rate: 72%                │ │
│ └──────────────────────────┘ │
│ ┌──────────────────────────┐ │
│ │ Apr 2 - Eng 201          │ │
│ │ ...                      │ │
│ └──────────────────────────┘ │
├──────────────────────────────┤
│      [ Export PDF ]          │  ← Bottom button, enabled when data loaded
└──────────────────────────────┘
```

Tapping a session card navigates to / expands student-by-student breakdown for that session.

### Alerts Sub-Tab

Renders existing `FacultyAlertsScreen` content (Today/Week/All filters, alert cards). No changes to alerts logic.

## Backend — PDF Export Endpoint

### Endpoint

```
GET /api/v1/attendance/export/pdf
```

### Query Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `schedule_ids` | string | Yes | Comma-separated UUIDs, or "all" |
| `start_date` | string (ISO date) | Yes | Range start |
| `end_date` | string (ISO date) | Yes | Range end |

### Auth

Requires faculty JWT. Validates that requested schedule_ids belong to the authenticated faculty.

### Response

`StreamingResponse` with `Content-Type: application/pdf`.

### PDF Content (ReportLab platypus)

- **Header:** "Attendance Report" + faculty name + date range + generation timestamp
- **Per-class section:**
  - Class title: subject code + name + room
  - Summary row: Total Sessions, Present, Late, Absent, Early Leave, Attendance Rate
  - Detailed table columns: Date | Student Name | Student Number | Status | Check-in Time | Presence Score
  - Rows sorted by date, then student name
- **Footer:** Page numbers

### New Dependency

`reportlab` added to `backend/requirements.txt`

### Service Layer

New file: `backend/app/services/pdf_service.py`
- `generate_attendance_pdf(schedules, records, faculty_name, date_range) -> bytes`
- Uses `SimpleDocTemplate`, `Table`, `TableStyle`, `Paragraph` from `reportlab.platypus`
- No new repository methods needed — existing `AttendanceRepository` + `ScheduleRepository` queries suffice

## Data Flow & API Integration (Mobile)

### History Data Fetching

1. **Schedule list:** Reuse existing faculty schedules endpoint on init
2. **Attendance records:** Use existing `GET /attendance` with `schedule_id`, `start_date`, `end_date`. Parallel requests per selected schedule.
3. **Summary stats:** Use existing `GET /attendance/schedule/{id}/summary` with date range. Parallel requests per selected schedule.
4. **PDF export:** New `GET /attendance/export/pdf` with same filters. Returns binary PDF.

### New ViewModel: `FacultyHistoryViewModel`

**State:**
- `selectedSchedules: List<ScheduleResponse>`
- `startDate: LocalDate`, `endDate: LocalDate`
- `isLoading: Boolean`, `isExporting: Boolean`
- `attendanceRecords: List<AttendanceRecordResponse>`
- `summaryStats: AttendanceSummaryResponse`
- `error: String?`

**Methods:**
- `loadHistory()` — fetch records + summary for selected filters
- `exportPdf()` — download PDF, save to cache, open share sheet
- `selectSchedules(schedules)`, `setDateRange(start, end)`

### PDF Download Handling

OkHttp downloads PDF bytes → write to `context.cacheDir` → open via `FileProvider` + `ACTION_VIEW` intent.

### New ApiService Method

```kotlin
@GET("attendance/export/pdf")
@Streaming
suspend fun exportAttendancePdf(
    @Query("schedule_ids") scheduleIds: String,
    @Query("start_date") startDate: String,
    @Query("end_date") endDate: String,
): Response<ResponseBody>
```

## Files Changed

### Backend (new)
- `backend/app/services/pdf_service.py` — ReportLab PDF generation
- New route in `backend/app/routers/attendance.py` — `/export/pdf` endpoint
- `reportlab` in `backend/requirements.txt`

### Android (new)
- `FacultyHistoryScreen.kt` — History screen with Attendance/Alerts tabs
- `FacultyHistoryViewModel.kt` — state management

### Android (modified)
- `IAMSNavHost.kt` — replace Alerts tab with History, add route
- `Routes.kt` — add `FACULTY_HISTORY` constant
- `ApiService.kt` — add `exportAttendancePdf()` method

### Android (unchanged, reused)
- `FacultyAlertsScreen.kt` — rendered as composable within Alerts sub-tab
- `FacultyAlertsViewModel.kt` — no changes
