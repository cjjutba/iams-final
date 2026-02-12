# Business Rules

## Auth Rules
1. All user-facing endpoints (FUN-07-06) require Supabase JWT (`Authorization: Bearer <token>`).
2. GET /presence/{attendance_id}/logs requires faculty or admin role.
3. GET /presence/early-leaves requires faculty or admin role.
4. Return 401 for missing/invalid JWT, 403 for insufficient role.
5. System-internal functions (FUN-07-01 to FUN-07-05) do not require JWT.

## Timezone Rules
1. `TIMEZONE` env var configures session timezone (default: Asia/Manila, +08:00).
2. Session date/time boundaries use the configured timezone, not UTC.
3. "Today" queries for session context use configured timezone.
4. All timestamps in responses include timezone offset (e.g., `+08:00`).

## Session Rules
1. Presence processing is scoped to one `(schedule_id, date)` session.
2. Session uses configured start/end boundaries from `schedules` table with `TIMEZONE` applied.
3. Only enrolled students (from `enrollments` table) are tracked for session state.

## Scan and Counter Rules
1. Scan interval defaults to 60 seconds (`SCAN_INTERVAL` env var, configurable).
2. Detected student resets miss counter to 0 and updates `last_seen`.
3. Undetected student increments miss counter by 1.
4. Counter must never go negative.
5. Recovery detection (re-appearance after misses) resets counter deterministically.

## Early-Leave Rules
1. Default threshold is 3 consecutive misses (`EARLY_LEAVE_THRESHOLD` env var, configurable).
2. Early-leave event is created once per `(attendance_id, schedule_id, date)` context — no duplicates.
3. Flagging updates attendance record status: `present` → `early_leave` (via MOD-06).
4. Flagging triggers downstream notification via MOD-08 WebSocket broadcast.

## Score Rules
1. Presence score = `(scans_detected / total_scans) × 100`.
2. Score updates remain consistent with presence log totals.
3. If `total_scans` is zero, score defaults to 0 (safe baseline).

## Access Rules
1. Faculty can view presence logs and early-leave events for schedules they are assigned to.
2. Admin can view presence data for any schedule.
3. Students cannot access MOD-07 endpoints directly (403). They see attendance status via MOD-06.

## Data Integrity Rules
1. Presence logs must reference valid attendance records (FK: `attendance_id` → `attendance_records.id`).
2. Early-leave events must reference valid attendance records and schedules.
3. Event timestamps should be monotonic within session context.
4. Duplicate early-leave events for same `(attendance_id, schedule_id, date)` context are prevented.
5. User deletion (MOD-02) cascades: `users` → `attendance_records` (MOD-06) → `presence_logs` + `early_leave_events` (MOD-07).
6. Schedule deactivation preserves existing presence records (soft boundary).
