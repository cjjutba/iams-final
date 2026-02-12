# Function Specifications

## FUN-06-01 Mark Attendance

**Auth:** System/internal — triggered by recognition pipeline (MOD-03/MOD-07). Not a user-facing endpoint.

Goal:
- Upsert attendance row from recognition event with dedup protections.

Inputs:
- `student_id` (UUID, FK → users.id) — recognized user.
- `schedule_id` (UUID, FK → schedules.id) — active schedule context.
- `timestamp` (TIMESTAMP WITH TIME ZONE) — detection time.

Process:
1. Resolve active schedule for timestamp context (day_of_week + time window + TIMEZONE env var).
2. Derive `date` from timestamp in configured timezone.
3. Check existing attendance row for `(student_id, schedule_id, date)`.
4. If missing, create row with `status=present`, `check_in_time=timestamp`.
5. If present, update relevant fields (e.g., last seen time for presence tracking).

Outputs:
- Attendance row created/updated.
- Response: `{ "success": true, "data": { "id": "uuid", ... }, "message": "Attendance marked" }`

Validation Rules:
- Prevent duplicate rows (UNIQUE constraint on `student_id + schedule_id + date`).
- Ignore unknown or unauthorized user context (no valid user → skip).
- Validate schedule_id exists and is active.

---

## FUN-06-02 Get Today's Attendance

**Auth:** Supabase JWT required. Faculty or admin role only. 401 for missing JWT, 403 for student role.

Goal:
- Return today's class attendance records and summary for a given schedule.

Inputs:
- `schedule_id` (UUID, query param) — required.
- Supabase JWT (`Authorization: Bearer <token>`).

Process:
1. Validate JWT and role (faculty/admin).
2. Validate schedule_id exists (404 if not found).
3. Determine "today" using configured timezone (TIMEZONE env var).
4. Query attendance rows for `(schedule_id, date=today)`.
5. Compute summary counts by status (present, late, absent, early_leave).

Outputs:
- Schedule info, attendance records array, summary counts.
- Response: `{ "success": true, "data": { "schedule": {...}, "records": [...], "summary": {...} }, "message": "" }`

Validation Rules:
- Return 404 for unknown schedule_id.
- Return 401 for missing/invalid JWT.
- Return 403 for student role.

---

## FUN-06-03 Get My Attendance

**Auth:** Supabase JWT required. Any authenticated user (role-scoped). Students see own records; faculty see own classes.

Goal:
- Return authenticated user's attendance history within date range.

Inputs:
- `start_date` (YYYY-MM-DD, query param) — optional.
- `end_date` (YYYY-MM-DD, query param) — optional.
- Supabase JWT (`Authorization: Bearer <token>`).

Process:
1. Validate JWT. Extract user_id from JWT `sub` claim and `role`.
2. Validate date range (start_date ≤ end_date if both provided).
3. If student role: query attendance rows where `student_id = user_id`.
4. If faculty role: query attendance rows for schedules where `faculty_id = user_id`.
5. Apply date filters if provided.
6. Return sorted history entries (date DESC).

Outputs:
- Attendance history list with schedule context.
- Response: `{ "success": true, "data": [...], "message": "" }`

Validation Rules:
- Return 401 for missing/invalid JWT.
- Invalid date ranges (start_date > end_date) return 422 validation error.
- Students can ONLY see their own records (enforced by JWT sub).

---

## FUN-06-04 Get Attendance History

**Auth:** Supabase JWT required. Faculty or admin role only. 401 for missing JWT, 403 for student role.

Goal:
- Return filtered attendance records for class/reporting context.

Inputs:
- `schedule_id` (UUID, query param) — required.
- `start_date` (YYYY-MM-DD, query param) — optional.
- `end_date` (YYYY-MM-DD, query param) — optional.
- Supabase JWT (`Authorization: Bearer <token>`).

Process:
1. Validate JWT and role (faculty/admin).
2. Validate schedule_id exists (404 if not found).
3. Faculty: verify they are assigned to the schedule (faculty_id match) or return 403.
4. Admin: unrestricted access to any schedule.
5. Apply date filters. Return result set sorted by date DESC.

Outputs:
- Filtered attendance data with student details.
- Response: `{ "success": true, "data": [...], "message": "" }`

Validation Rules:
- Return 401 for missing/invalid JWT.
- Return 403 for student role or unassigned faculty.
- Return 404 for non-existent schedule_id.
- Missing date filters default to all available records for that schedule.

---

## FUN-06-05 Manual Attendance Entry

**Auth:** Supabase JWT required. Faculty or admin role only. 401 for missing JWT, 403 for student role.

Goal:
- Allow faculty to insert/update attendance status manually with audit remarks.

Inputs:
- Request body:
  - `student_id` (UUID) — required.
  - `schedule_id` (UUID) — required.
  - `date` (YYYY-MM-DD) — required.
  - `status` (string, one of: `present`, `late`, `absent`, `early_leave`) — required.
  - `remarks` (string) — required for audit trail.
- Supabase JWT (`Authorization: Bearer <token>`).

Process:
1. Validate JWT and role (faculty/admin).
2. Validate student_id exists (FK → users.id, must be student role).
3. Validate schedule_id exists (FK → schedules.id).
4. Validate status is one of allowed values.
5. Upsert attendance row for `(student_id, schedule_id, date)`.
6. Store `remarks`, `updated_by` (JWT sub), `updated_at` (current timestamp).

Outputs:
- Created/updated attendance record with audit metadata.
- Response: `{ "success": true, "data": { "id": "uuid", ... }, "message": "Attendance updated manually" }`

Validation Rules:
- Return 401 for missing/invalid JWT.
- Return 403 for student role.
- Return 404 for non-existent student_id or schedule_id.
- Return 422 for invalid status value or missing remarks.

---

## FUN-06-06 Get Live Attendance

**Auth:** Supabase JWT required. Faculty or admin role only. 401 for missing JWT, 403 for student role.

Goal:
- Return active class roster with current attendance/session indicators.

Inputs:
- `schedule_id` (UUID, path param) — required.
- Supabase JWT (`Authorization: Bearer <token>`).

Process:
1. Validate JWT and role (faculty/admin).
2. Validate schedule_id exists (404 if not found).
3. Check if schedule has an active session (is_active + day_of_week + time window in configured timezone).
4. If active: resolve current scan/detection state from presence tracking (MOD-07).
5. Return per-student live status fields (detected/not detected, last seen time).

Outputs:
- Live attendance payload with session metadata.
- Response: `{ "success": true, "data": { "schedule": {...}, "session_active": true, "students": [...] }, "message": "" }`

Validation Rules:
- Return 404 for non-existent schedule_id.
- Return clear response when session not active: `{ "success": true, "data": { "session_active": false }, "message": "No active session" }`.
- Return 401 for missing/invalid JWT.
- Return 403 for student role.
