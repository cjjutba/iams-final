# Business Rules

## Auth Rules
1. All MOD-06 user-facing endpoints require Supabase JWT (`Authorization: Bearer <token>`).
2. FUN-06-05 (Manual Attendance) and FUN-06-02/04/06 (Today/History/Live) require faculty or admin role.
3. FUN-06-03 (My Attendance) is role-scoped: students see own records, faculty see own classes.
4. Missing or invalid JWT returns 401. Insufficient role returns 403.
5. No API key auth — that pattern is for MOD-03/MOD-04 edge devices only.

## Attendance State Rules
1. Allowed statuses: `present`, `late`, `absent`, `early_leave`.
2. Attendance row uniqueness is `(student_id, schedule_id, date)` — enforced at database level with UNIQUE constraint.
3. Check-in is first detection; later detections update session context (last seen time for presence tracking).
4. Status transitions: system can update status (e.g., present → early_leave if MOD-07 detects early departure).

## Timezone Rules
1. All date/time comparisons use `TIMEZONE` env var (default: `Asia/Manila`, UTC+08:00 for JRMSU pilot).
2. "Today" is determined by the current date in the configured timezone, not UTC.
3. `check_in_time` is stored as TIMESTAMP WITH TIME ZONE. Display uses configured timezone.
4. Date range filters (`start_date`, `end_date`) are interpreted as dates in the configured timezone.

## Query Rules
1. Date filters are inclusive (`start_date ≤ date ≤ end_date`) and validated (start_date ≤ end_date).
2. Today's attendance is scoped to schedule_id and current date (in configured timezone).
3. Personal history (FUN-06-03) returns only own records for students (enforced by JWT sub claim).
4. Faculty history access (FUN-06-04) is restricted to assigned schedules (faculty_id match) unless admin.
5. Results sorted by date DESC by default.

## Manual Override Rules
1. Faculty or admin role required for manual entries (403 for student role).
2. Manual action must store `remarks` (required), `updated_by` (JWT sub), and `updated_at` (current timestamp).
3. Manual update respects uniqueness constraint — upserts on `(student_id, schedule_id, date)`.
4. Status must be one of the allowed values (422 for invalid status).

## Access Rules
1. Student cannot access faculty-only endpoints (GET /today, GET /history, POST /manual, GET /live). Returns 403.
2. Faculty can only access attendance data for their own assigned schedules (faculty_id match). Returns 403 for unassigned schedules.
3. Admin has unrestricted access to all attendance data across all schedules.
4. FUN-06-01 (Mark Attendance) is a system operation — not exposed as a user-facing endpoint.

## Data Integrity Rules
1. `student_id` must reference a valid user with student role (FK → users.id).
2. `schedule_id` must reference a valid schedule (FK → schedules.id).
3. User deletion (MOD-02) should cascade to attendance records for data integrity.
4. Schedule deactivation preserves attendance records (historical data).
