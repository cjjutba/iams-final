# Acceptance Criteria

## Function-Level Acceptance

### FUN-06-01 (Mark Attendance)
- Given recognized student and active schedule, attendance row is created/updated.
- Duplicate rows for same student/schedule/date are not created (UNIQUE constraint enforced).
- Unknown student_id or inactive schedule is silently skipped (no error, no record).
- `check_in_time` uses detection timestamp in configured timezone.

### FUN-06-02 (Get Today's Attendance)
- Given valid Supabase JWT with faculty/admin role and valid schedule_id, returns today's records and summary.
- Summary includes counts: `{ present: N, late: N, absent: N, early_leave: N }`.
- Unknown schedule_id returns 404.
- Missing/invalid JWT returns 401.
- Student role returns 403.
- "Today" is determined by configured timezone (TIMEZONE env var).
- Response includes `"message"` field.

### FUN-06-03 (Get My Attendance)
- Student receives own attendance records for requested date range.
- Faculty receives attendance records for their assigned classes.
- Invalid date range (start_date > end_date) returns 422 validation error.
- Missing/invalid JWT returns 401.
- Results sorted by date DESC.
- Response includes `"message"` field.

### FUN-06-04 (Get Attendance History)
- Given valid JWT with faculty/admin role, returns filtered attendance data for a schedule.
- Faculty can only query their own assigned schedules (faculty_id match). Unassigned schedule returns 403.
- Admin has unrestricted access to any schedule.
- Missing/invalid JWT returns 401. Student role returns 403.
- 404 for non-existent schedule_id.
- Response includes `"message"` field.

### FUN-06-05 (Manual Attendance Entry)
- Faculty/admin can create/update manual attendance with required `remarks`.
- Student caller returns 403.
- Missing/invalid JWT returns 401.
- Invalid status value returns 422.
- Non-existent student_id or schedule_id returns 404.
- Audit fields stored: `remarks`, `updated_by` (JWT sub), `updated_at`.
- Response includes `"message": "Attendance updated manually"`.

### FUN-06-06 (Get Live Attendance)
- Active session returns live roster payload with per-student detection status.
- Inactive session returns `{ "session_active": false }` with `"message": "No active session"`.
- Missing/invalid JWT returns 401. Student role returns 403.
- 404 for non-existent schedule_id.
- Response includes `"message"` field.

## Module-Level Acceptance
- Manual overrides are auditable (remarks + updated_by + updated_at stored).
- History and today's views are consistent with source records.
- Live attendance data aligns with session state from MOD-07 presence tracking.
- All date/time operations use configured timezone (TIMEZONE env var, default: Asia/Manila).
- Response envelope format consistent: `{ "success": true, "data": {}, "message": "" }` for success; `{ "success": false, "error": { "code": "", "message": "" } }` for errors.
- Auth enforcement: 401 for missing/invalid JWT, 403 for insufficient role on all protected endpoints.
