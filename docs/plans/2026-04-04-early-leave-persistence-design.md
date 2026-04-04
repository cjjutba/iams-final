# Early Leave Persistence Design

## Problem

When a student leaves early and returns, the system erases the early leave from the live feed, history, and analytics. The attendance status is restored to PRESENT/LATE and the early leave event becomes invisible. Faculty need to see that a student left early even after they return — for accountability and logging purposes.

## Design

### Principle

Early leave events are **permanent log entries**. A student's *current status* reflects reality (Present/Late), but the *event record* persists across all views: live feed, alerts, history, and analytics.

### Backend Changes

#### TrackPresenceService (track_presence_service.py)

**Current:** On return, resets `early_leave_flagged = False` and `early_leave_returned = False`, restoring attendance status. The student vanishes from the early leave summary.

**New:** On return:
- Keep `early_leave_flagged = True`
- Set `early_leave_returned = True`
- Restore attendance record status to PRESENT/LATE (unchanged)
- Update `EarlyLeaveEvent.returned = True, returned_at = now` in DB
- Do NOT reset flags — student stays visible in early leave summaries
- Allow re-flagging: if student leaves again after return, create a new EarlyLeaveEvent and reset `early_leave_returned = False`

#### get_attendance_summary() changes

**Current arrays:** `present`, `late`, `absent`, `early_leave` (mutually exclusive for early leave)

**New arrays:** Keep existing + add `early_leave_returned`:
- `present` / `late`: includes returned early-leave students (current status)
- `early_leave`: students flagged AND still absent (not returned)
- `early_leave_returned`: students flagged AND returned (includes return timestamp)

Students who returned appear in BOTH `present`/`late` AND `early_leave_returned`.

#### EarlyLeaveEvent updates

Populate the existing `returned` and `returned_at` fields (currently never written):
```python
# On student return:
event = db.query(EarlyLeaveEvent).filter(
    attendance_id == state.attendance_id,
    returned == False
).order_by(detected_at.desc()).first()
if event:
    event.returned = True
    event.returned_at = datetime.now()
    event.absence_duration_seconds = int(now_mono - state.absent_since)
```

#### /attendance/alerts endpoint

Add `returned` and `returned_at` to `AlertResponse`. Sort results: "Still Absent" (returned=False) first, then "Returned" (returned=True), both ordered by detected_at DESC.

### Android Changes

#### Live Feed — Attendance Tab

**Dual display:** A returned student appears in:
1. **Present section** (or Late) — with normal green/orange dot
2. **Early Leave section** — with "↩ Returned" badge and timestamps

Early Leave section shows ALL flagged students:
- Still absent: name + "Left at {time}" (no badge)
- Returned: name + "↩ Returned" badge + "Left {time} · Back {time}"

#### Alerts Screen

Each alert card shows:
- "Still Absent" badge (red-ish) or "✓ Returned" badge (neutral)
- Returned alerts include `returned_at` timestamp
- Sort order: Still Absent first, Returned second

#### History Screen

- Session summary card gains "Early Leave" count column (count of EarlyLeaveEvent records for that session, regardless of return status)
- Detail rows show early leave events: "Left at {time}, Returned at {time} ({duration} absence)" or "Left at {time} — did not return"

### WebSocket Message Changes

`attendance_summary` message adds `early_leave_returned` array:
```json
{
  "type": "attendance_summary",
  "present": [...],
  "late": [...],
  "absent": [...],
  "early_leave": [{"user_id": "...", "name": "..."}],
  "early_leave_returned": [
    {"user_id": "...", "name": "...", "left_at": "15:10", "returned_at": "15:18"}
  ]
}
```

### Files Affected

**Backend:**
- `backend/app/services/track_presence_service.py` — return logic, summary generation
- `backend/app/services/realtime_pipeline.py` — event handling for return
- `backend/app/routers/attendance.py` — alerts endpoint response, live attendance
- `backend/app/schemas/attendance.py` — AlertResponse fields

**Android:**
- `android/.../data/model/Models.kt` — AttendanceSummaryMessage, AlertResponse fields
- `android/.../data/api/AttendanceWebSocketClient.kt` — parse new summary field
- `android/.../ui/faculty/FacultyLiveFeedViewModel.kt` — track returned students
- `android/.../ui/faculty/FacultyLiveFeedScreen.kt` — dual display in Attendance tab
- `android/.../ui/faculty/FacultyHistoryScreen.kt` — early leave count + detail rows
- `android/.../ui/faculty/FacultyAlertsViewModel.kt` — sort by returned status
- Alert card composable — returned/still-absent badge
