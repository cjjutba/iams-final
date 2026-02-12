# Acceptance Criteria

## Function-Level Acceptance

### FUN-07-01 (Start and Manage Session)
- Session initializes correctly for valid active schedule/date using configured `TIMEZONE`.
- Invalid session context (non-existent schedule, inactive schedule) is rejected.
- Session state is scoped to `(schedule_id, date)`.

### FUN-07-02 (Run Periodic Scan)
- Periodic scans update detection state without loop failure.
- Scan interval obeys configured `SCAN_INTERVAL` value (default: 60s).
- Presence log entries are created per scan cycle.

### FUN-07-03 (Maintain Miss Counters)
- Consecutive misses increment counter by 1.
- Recovery detection resets counter to zero deterministically.
- Counter never goes negative.

### FUN-07-04 (Flag Early Leave)
- Early-leave event is flagged when `EARLY_LEAVE_THRESHOLD` (default: 3) consecutive misses reached.
- Duplicate flags for same `(attendance_id, schedule_id, date)` context are prevented.
- Attendance status updated to `early_leave` via MOD-06.

### FUN-07-05 (Compute Presence Score)
- Presence score calculation matches scan counts: `(scans_detected / total_scans) × 100`.
- Zero-scan case handled safely (returns 0).

### FUN-07-06 (Return Presence Data)
- Presence log endpoint returns scan records for `attendance_id`.
- Early-leave endpoint returns schedule/date-specific events.
- **Auth: 401** returned for missing or invalid JWT.
- **Auth: 403** returned for student role attempting to access faculty-only endpoints.
- **Auth: 403** returned for expired JWT.
- Empty results return empty list (not 404).
- Response follows envelope format: `{ "success": true, "data": {}, "message": "" }`.

## Module-Level Acceptance
- Early-leave and recovery scenarios behave as documented.
- Presence data aligns with attendance status updates (MOD-06).
- Query endpoints support faculty detail and alert screens (SCR-022, SCR-023, SCR-025).
- Auth enforcement: all FUN-07-06 endpoints reject unauthenticated requests (401) and unauthorized roles (403).
- Response envelope format consistent across all endpoint responses (no `details` array in errors).
- Session boundaries and "today" queries use configured `TIMEZONE` env var correctly.
- Timestamps in responses include timezone offset (e.g., `+08:00`).
