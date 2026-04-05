# Early Leave Persistence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make early leave events permanent log entries that remain visible in live feed, alerts, history, and analytics even after a student returns.

**Architecture:** Backend keeps `early_leave_flagged = True` after return (instead of resetting), populates `EarlyLeaveEvent.returned/returned_at`, and adds `early_leave_returned` array to WebSocket summaries. Android shows returned students in both Present AND Early Leave sections. Alerts show returned/still-absent badges.

**Tech Stack:** Python/FastAPI (backend services + schemas), Kotlin/Jetpack Compose (Android UI), WebSocket (real-time updates)

---

### Task 1: Fix TrackPresenceService Return Logic

**Files:**
- Modify: `backend/app/services/track_presence_service.py:193-216`

**Step 1: Update the return handler**

Replace lines 193-216 (the `elif state.early_leave_flagged and not state.early_leave_returned:` block):

```python
elif state.early_leave_flagged and not state.early_leave_returned:
    # Returned after early leave — restore status but keep flag for logging
    state.early_leave_returned = True
    state.absent_since = None
    state.last_presence_start = now_mono

    # Restore attendance record to original status (PRESENT/LATE)
    restored_status = state.status
    self.attendance_repo.update(state.attendance_id, {
        "status": restored_status,
    })

    # Persist return to EarlyLeaveEvent record
    from sqlalchemy import desc
    early_event = (
        self.db.query(EarlyLeaveEvent)
        .filter(
            EarlyLeaveEvent.attendance_id == state.attendance_id,
            EarlyLeaveEvent.returned == False,
        )
        .order_by(desc(EarlyLeaveEvent.detected_at))
        .first()
    )
    if early_event:
        early_event.returned = True
        early_event.returned_at = datetime.now()
        if state.absent_since is not None:
            early_event.absence_duration_seconds = int(now_mono - state.absent_since)
        self.db.commit()

    events.append({
        "event": "early_leave_return",
        "student_id": sid,
        "student_name": state.name,
        "restored_status": restored_status.value,
        "returned_at": datetime.now().isoformat(),
    })
    logger.info("Student %s returned after early leave, restored to %s", sid, restored_status.value)
```

Key changes from current code:
- Do NOT reset `early_leave_flagged = False` (keep it True for summary visibility)
- Do NOT reset `early_leave_returned = False`
- Add `EarlyLeaveEvent.returned = True` and `returned_at` DB update
- Add `returned_at` to the event dict

**Step 2: Handle re-flagging after return**

In the "Student NOT detected" block (lines 234-275), the condition `not state.early_leave_flagged` prevents re-detection after return. Update line 234:

```python
if state.status != AttendanceStatus.ABSENT and (not state.early_leave_flagged or state.early_leave_returned):
```

This allows a student who returned (`early_leave_returned = True`) to be re-flagged if they leave again. When re-flagged:
- `state.early_leave_flagged` stays `True`
- `state.early_leave_returned` resets to `False`
- A new `EarlyLeaveEvent` is created

Add this reset right after line 240 (`state.early_leave_flagged = True`):

```python
state.early_leave_returned = False  # Reset return flag for new absence
```

**Step 3: Verify import exists**

Ensure `from sqlalchemy import desc` is available. Check top of file — if not present, add it alongside the existing `from sqlalchemy.orm import Session` import.

**Step 4: Run backend tests**

Run: `docker compose exec -T api-gateway pytest tests/ -q --ignore=tests/integration/test_auth_routes.py -x`
Expected: All schedule/presence/attendance tests pass

**Step 5: Commit**

```
feat(backend): persist early leave flag after student return

Keep early_leave_flagged=True when student returns so early leave
events remain visible in summaries. Populate EarlyLeaveEvent.returned
and returned_at fields. Allow re-flagging if student leaves again.
```

---

### Task 2: Update get_attendance_summary()

**Files:**
- Modify: `backend/app/services/track_presence_service.py:364-392`

**Step 1: Add early_leave_returned array to summary**

Replace `get_attendance_summary()` (lines 364-392):

```python
def get_attendance_summary(self) -> dict:
    """Build current attendance summary for WebSocket broadcast."""
    present = []
    absent = []
    late = []
    early_leave = []
    early_leave_returned = []

    for sid, state in self._students.items():
        info = {"user_id": sid, "name": state.name}

        if state.early_leave_flagged and not state.early_leave_returned:
            # Still absent after early leave
            early_leave.append(info)
        elif state.early_leave_flagged and state.early_leave_returned:
            # Returned after early leave — show in both present/late AND early_leave_returned
            early_leave_returned.append(info)
            if state.status == AttendanceStatus.LATE:
                late.append(info)
                present.append(info)
            elif state.status == AttendanceStatus.PRESENT:
                present.append(info)
        elif state.status == AttendanceStatus.ABSENT:
            absent.append(info)
        elif state.status == AttendanceStatus.LATE:
            late.append(info)
            present.append(info)
        elif state.status == AttendanceStatus.PRESENT:
            present.append(info)

    return {
        "type": "attendance_summary",
        "schedule_id": self.schedule_id,
        "present_count": len(present),
        "total_enrolled": len(self._students),
        "present": present,
        "absent": absent,
        "late": late,
        "early_leave": early_leave,
        "early_leave_returned": early_leave_returned,
    }
```

**Step 2: Run backend tests**

Run: `docker compose exec -T api-gateway pytest tests/ -q --ignore=tests/integration/test_auth_routes.py -x`
Expected: PASS

**Step 3: Commit**

```
feat(backend): add early_leave_returned array to attendance summary

Students who returned after early leave now appear in both
present/late AND early_leave_returned arrays in WebSocket summaries.
```

---

### Task 3: Add returned fields to AlertResponse

**Files:**
- Modify: `backend/app/schemas/attendance.py:200-227`
- Modify: `backend/app/routers/attendance.py:594-610`

**Step 1: Add fields to AlertResponse schema**

In `backend/app/schemas/attendance.py`, add after the `date` field (line 215):

```python
    returned: bool = False
    returned_at: datetime | None = None
    absence_duration_seconds: int | None = None
```

**Step 2: Populate fields in alerts endpoint**

In `backend/app/routers/attendance.py`, update the AlertResponse construction (lines 594-610) to include the new fields:

```python
alerts.append(
    AlertResponse(
        id=str(event.id),
        attendance_id=str(event.attendance_id),
        student_id=str(student.id),
        student_name=f"{student.first_name} {student.last_name}",
        student_student_id=student.student_id,
        schedule_id=str(attendance.schedule_id),
        subject_code=schedule.subject_code,
        subject_name=schedule.subject_name,
        detected_at=event.detected_at,
        last_seen_at=event.last_seen_at,
        consecutive_misses=event.consecutive_misses,
        notified=event.notified,
        date=attendance.date,
        returned=event.returned,
        returned_at=event.returned_at,
        absence_duration_seconds=event.absence_duration_seconds,
    )
)
```

**Step 3: Sort alerts — Still Absent first**

After building the `alerts` list (line 612), add sorting before the return:

```python
# Sort: still-absent first (more urgent), then by detected_at descending
alerts.sort(key=lambda a: (a.returned, -(a.detected_at.timestamp() if a.detected_at else 0)))
return alerts
```

**Step 4: Run backend tests**

Run: `docker compose exec -T api-gateway pytest tests/ -q --ignore=tests/integration/test_auth_routes.py -x`
Expected: PASS

**Step 5: Commit**

```
feat(backend): add returned/returned_at to alert responses

Alerts now include return status and timestamp. Sorted with
still-absent alerts first for urgency.
```

---

### Task 4: Update Android Models

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/data/model/Models.kt`

**Step 1: Add early_leave_returned to AttendanceSummaryMessage**

After the `earlyLeave` field (line 251):

```kotlin
@SerializedName("early_leave_returned") val earlyLeaveReturned: List<AttendanceSummaryStudent>?
```

**Step 2: Add returned fields to AlertResponse**

After the `notified` field (line 178):

```kotlin
val returned: Boolean = false,
@SerializedName("returned_at") val returnedAt: String? = null,
@SerializedName("absence_duration_seconds") val absenceDurationSeconds: Int? = null,
```

**Step 3: Commit**

```
feat(android): add early leave return fields to data models
```

---

### Task 5: Update LiveFeed ViewModel and WebSocket Handling

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedViewModel.kt`

**Step 1: Add earlyLeaveReturnedStudents to LiveFeedUiState**

After `earlyLeaveStudents` (line 35):

```kotlin
val earlyLeaveReturnedStudents: List<StudentAttendanceStatus> = emptyList(),
```

**Step 2: Update updateFromAttendanceSummary()**

Replace the method (lines 189-203):

```kotlin
private fun updateFromAttendanceSummary(summary: AttendanceSummaryMessage) {
    val present = summary.present?.map { toStudentStatus(it.userId, it.name, "present") } ?: emptyList()
    val absent = summary.absent?.map { toStudentStatus(it.userId, it.name, "absent") } ?: emptyList()
    val late = summary.late?.map { toStudentStatus(it.userId, it.name, "late") } ?: emptyList()
    val earlyLeave = summary.earlyLeave?.map { toStudentStatus(it.userId, it.name, "early_leave") } ?: emptyList()
    val earlyLeaveReturned = summary.earlyLeaveReturned?.map { toStudentStatus(it.userId, it.name, "early_leave") } ?: emptyList()

    _uiState.value = _uiState.value.copy(
        presentStudents = present,
        absentStudents = absent,
        lateStudents = late,
        earlyLeaveStudents = earlyLeave,
        earlyLeaveReturnedStudents = earlyLeaveReturned,
        presentCount = summary.presentCount,
        totalEnrolled = summary.totalEnrolled,
    )
}
```

**Step 3: Commit**

```
feat(android): track early leave returned students in ViewModel
```

---

### Task 6: Update LiveFeed Attendance Tab — Dual Display

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedScreen.kt:561-567`

**Step 1: Import EarlyLeaveBg if not already imported**

Check if `EarlyLeaveBg` is imported. If not, add alongside `EarlyLeaveFg`.

**Step 2: Update Early Leave section to include returned students**

Replace the Early Leave section (lines 561-567):

```kotlin
// Early Leave — combine still-absent and returned
val allEarlyLeave = uiState.earlyLeaveStudents + uiState.earlyLeaveReturnedStudents
if (allEarlyLeave.isNotEmpty()) {
    item { AttendanceSectionLabel("Early Leave (${allEarlyLeave.size})", com.iams.app.ui.theme.EarlyLeaveFg) }

    // Still absent (no badge)
    items(uiState.earlyLeaveStudents) { student ->
        StudentRow(student = student, dotColor = com.iams.app.ui.theme.EarlyLeaveFg)
        HorizontalDivider(color = Border, thickness = 0.5.dp)
    }

    // Returned (with badge)
    items(uiState.earlyLeaveReturnedStudents) { student ->
        EarlyLeaveReturnedRow(student = student)
        HorizontalDivider(color = Border, thickness = 0.5.dp)
    }
}
```

**Step 3: Create EarlyLeaveReturnedRow composable**

Add before the `EarlyLeaveTimeoutDialog` composable (around line 947):

```kotlin
@Composable
private fun EarlyLeaveReturnedRow(student: StudentAttendanceStatus) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.sm),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Half-filled circle to indicate returned
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(com.iams.app.ui.theme.EarlyLeaveFg.copy(alpha = 0.4f))
        )
        Spacer(modifier = Modifier.width(spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = student.studentName,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = TextPrimary,
                maxLines = 1
            )
            val displayId = student.studentNumber ?: student.studentId.take(8)
            Text(
                text = displayId,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }
        // Returned badge
        Text(
            text = "↩ Returned",
            style = MaterialTheme.typography.labelSmall,
            color = PresentFg,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier
                .clip(RoundedCornerShape(4.dp))
                .background(PresentBg)
                .padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}
```

**Step 4: Build Android**

Run: `cd android && ./gradlew compileDebugKotlin`
Expected: BUILD SUCCESSFUL

**Step 5: Commit**

```
feat(android): dual display for early leave in live feed

Students who returned after early leave now appear in both the Present
section and the Early Leave section with a "↩ Returned" badge.
```

---

### Task 7: Update Alerts Screen with Return Badges

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyAlertsScreen.kt:204-246`

**Step 1: Update AlertCard to show returned badge**

Update the `AlertCard` composable to include a returned/still-absent badge. After the student name Text (line 229), add:

```kotlin
// Return status badge
Row(verticalAlignment = Alignment.CenterVertically) {
    Text(
        text = alert.studentName ?: "Unknown Student",
        style = MaterialTheme.typography.bodyLarge,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.weight(1f),
    )
    if (alert.returned) {
        Text(
            text = "✓ Returned",
            style = MaterialTheme.typography.labelSmall,
            color = PresentFg,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier
                .clip(RoundedCornerShape(4.dp))
                .background(PresentBg)
                .padding(horizontal = 6.dp, vertical = 2.dp)
        )
    } else {
        Text(
            text = "Still Absent",
            style = MaterialTheme.typography.labelSmall,
            color = AbsentFg,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier
                .clip(RoundedCornerShape(4.dp))
                .background(AbsentBg)
                .padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}
```

Replace the existing student name `Text` + the message `Text` below it with this Row + an updated message that includes return time:

```kotlin
// Updated message with return info
val displayMessage = if (alert.returned && alert.returnedAt != null) {
    "Left early · Returned at ${formatTime(alert.returnedAt)}"
} else {
    alert.message ?: "Early leave detected"
}
Text(
    text = displayMessage,
    style = MaterialTheme.typography.bodySmall,
    color = TextSecondary,
)
```

Add a `formatTime` helper if not already present (parse ISO datetime, display HH:mm).

**Step 2: Import PresentFg, PresentBg, AbsentBg if not already imported**

Check the file's imports and add any missing theme colors.

**Step 3: Build Android**

Run: `cd android && ./gradlew compileDebugKotlin`
Expected: BUILD SUCCESSFUL

**Step 4: Commit**

```
feat(android): add returned/still-absent badges to alert cards

Alert cards now show "✓ Returned" (green) or "Still Absent" (red)
badges. Returned alerts include the return timestamp.
```

---

### Task 8: Update Faculty History — Early Leave Count

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHistoryScreen.kt` (find the session summary card)

**Step 1: Explore the current history summary card**

Read `FacultyHistoryScreen.kt` to find where Present/Late/Absent counts are displayed. The backend's `/attendance/schedule-summaries` already returns `early_leave_count` in `AttendanceSummaryResponse` — verify this field exists in the Android model.

**Step 2: Add Early Leave count to the summary display**

In the session summary card (where Present, Late, Absent are shown), add an "Early Leave" stat using the `EarlyLeaveFg` color. Follow the same pattern as the existing stat items.

**Step 3: Build and commit**

Run: `cd android && ./gradlew compileDebugKotlin`

```
feat(android): show early leave count in history summary
```

---

### Task 9: Final Verification

**Step 1: Run all backend tests**

Run: `docker compose exec -T api-gateway pytest tests/ -q --ignore=tests/integration/test_auth_routes.py`
Expected: All pass, no regressions

**Step 2: Build full Android APK**

Run: `cd android && ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL

**Step 3: Manual verification checklist**

- [ ] Start a session, student checks in → shows in Present
- [ ] Student leaves frame for 5+ minutes → shows in Early Leave, notification sent
- [ ] Student returns → shows in BOTH Present AND Early Leave (with "↩ Returned" badge)
- [ ] Alerts screen shows "✓ Returned" badge, still-absent alerts sort first
- [ ] History screen shows Early Leave count in summary
- [ ] End session → attendance record final status is PRESENT/LATE (not EARLY_LEAVE)
- [ ] EarlyLeaveEvent in DB has `returned=true` and `returned_at` populated

**Step 4: Commit any remaining changes**

```
chore: verify early leave persistence across all views
```
