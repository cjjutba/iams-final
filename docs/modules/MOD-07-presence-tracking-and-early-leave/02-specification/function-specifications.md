# Function Specifications

## Function Categories
- **System-Internal**: FUN-07-01 to FUN-07-05 (no HTTP endpoints, invoked by presence service scan loop).
- **User-Facing API**: FUN-07-06 (exposed as GET /presence/* HTTP endpoints, requires Supabase JWT).

---

## FUN-07-01 Start and Manage Session State

**Auth:** System-internal — no JWT required (invoked by backend presence service).

**Goal:**
- Initialize and maintain session state for schedule/date context.

**Inputs:**
- `schedule_id` (UUID) — FK → `schedules.id`.
- `date` (DATE) — session date in configured `TIMEZONE`.
- Enrolled student set from `enrollments` table.

**Process:**
1. Resolve active schedule/session boundaries using `TIMEZONE` env var.
2. Initialize per-student state fields (miss_count=0, detected=false, last_seen=null).
3. Track session lifecycle (start → active → end).

**Outputs:**
- Session state object bound to `(schedule_id, date)`.

**Validation Rules:**
- Reject invalid/non-active schedule context.
- Ensure timezone-consistent date/time handling using configured `TIMEZONE`.

---

## FUN-07-02 Run Periodic Scan

**Auth:** System-internal — no JWT required.

**Goal:**
- Execute scan cycle and update detection state.

**Inputs:**
- Latest detection set (from MOD-03/MOD-04 recognition pipeline).
- Current session state.

**Process:**
1. Iterate enrolled students.
2. Determine detected/not-detected status per scan.
3. Update scan counters and create presence log entries.
4. Interval: `SCAN_INTERVAL` env var (default: 60 seconds).

**Outputs:**
- Updated per-student scan state and `presence_logs` entries.

**Validation Rules:**
- Scan interval should use configured `SCAN_INTERVAL` value.
- Missing detections should not break loop.

---

## FUN-07-03 Maintain Miss Counters

**Auth:** System-internal — no JWT required.

**Goal:**
- Track consecutive misses and recovery resets.

**Inputs:**
- Per-student detection result from FUN-07-02.

**Process:**
1. If detected: reset `miss_count` to 0, update `last_seen` timestamp.
2. If not detected: increment `miss_count` by 1.
3. Persist counter and last-seen updates.

**Outputs:**
- Updated `miss_count` and `last_seen` fields per student.

**Validation Rules:**
- Counter must never go negative.
- Recovery detection should reset to zero deterministically.

---

## FUN-07-04 Flag Early Leave

**Auth:** System-internal — no JWT required.

**Goal:**
- Create early-leave event once threshold condition is met.

**Inputs:**
- Per-student `miss_count`.
- `EARLY_LEAVE_THRESHOLD` env var (default: 3).

**Process:**
1. Compare `miss_count` against `EARLY_LEAVE_THRESHOLD`.
2. If threshold reached and not previously flagged for this `(attendance_id, schedule_id, date)` context: create `early_leave_events` record.
3. Update related attendance record status: `present` → `early_leave` (via MOD-06).
4. Emit event for MOD-08 WebSocket broadcast.

**Outputs:**
- `early_leave_events` record with `attendance_id`, `schedule_id`, `flagged_at` (TIMESTAMPTZ).
- Attendance status update in MOD-06.

**Validation Rules:**
- Avoid duplicate flagging for same `(attendance_id, schedule_id, date)` context.
- Threshold must be configurable via env var.

---

## FUN-07-05 Compute Presence Score

**Auth:** System-internal — no JWT required.

**Goal:**
- Compute student presence percentage for session.

**Inputs:**
- `total_scans` (INTEGER) — total scan cycles in session.
- `scans_detected` (INTEGER) — scans where student was detected.

**Process:**
1. Validate denominator (total_scans > 0).
2. Compute `score = (scans_detected / total_scans) × 100`.
3. Persist/update score in attendance context.

**Outputs:**
- Numeric presence score (FLOAT, 0-100).

**Validation Rules:**
- If `total_scans` is zero, return score of 0 (safe baseline).

---

## FUN-07-06 Return Presence Logs and Early-Leave Events

**Auth:** Supabase JWT required (`Authorization: Bearer <token>`). Role: faculty or admin. Returns 401 for missing/invalid JWT, 403 for insufficient role (e.g., student).

**Goal:**
- Expose presence logs and early-leave events through read APIs.

**Inputs:**
- `attendance_id` (UUID) — for presence log queries.
- `schedule_id` (UUID) + `date` (YYYY-MM-DD) — for early-leave event queries.

**Process:**
1. Verify Supabase JWT and extract role.
2. If role is not faculty or admin: return 403.
3. Validate query identifiers (attendance_id exists, schedule_id exists).
4. Query logs/events from respective tables.
5. Return response in envelope format.

**Outputs:**
- Presence log list:
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "id": "uuid",
        "attendance_id": "uuid",
        "scan_number": 1,
        "detected": true,
        "scanned_at": "2026-02-12T07:01:00+08:00"
      }
    ]
  },
  "message": "Presence logs retrieved successfully"
}
```
- Early-leave event list:
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "id": "uuid",
        "attendance_id": "uuid",
        "schedule_id": "uuid",
        "student_id": "uuid",
        "student_name": "John Doe",
        "student_id_number": "21-A-012345",
        "flagged_at": "2026-02-12T08:15:00+08:00",
        "consecutive_misses": 3
      }
    ]
  },
  "message": "Early-leave events retrieved successfully"
}
```

**Error Responses:**
```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid JWT"
  }
}
```

**Validation Rules:**
- Enforce faculty/admin role via Supabase JWT.
- Return 401 for missing/invalid JWT, 403 for insufficient role.
- Return empty lists when no records exist (not 404).
