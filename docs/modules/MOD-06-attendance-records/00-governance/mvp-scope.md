# MVP Scope

## In Scope
- Mark attendance from recognition events (system-triggered, dedup by `student_id + schedule_id + date`).
- Retrieve today's attendance for a class (faculty/admin, requires Supabase JWT + schedule_id).
- Retrieve personal student attendance history (student's own, with `start_date`/`end_date` filters).
- Retrieve filtered attendance history for class context (faculty/admin, by schedule_id + date range).
- Manual attendance entry by faculty (faculty/admin only, requires `remarks` for audit trail).
- Live attendance roster endpoint (faculty/admin, real-time for active class session).
- All endpoints secured with Supabase JWT; role-based access enforced.

## Out of Scope
- Advanced report export pipelines.
- Complex analytics/trend dashboards.
- Early leave detection algorithm internals (MOD-07).
- Rate limiting (thesis demonstration).
- Direct enrollment management (MOD-05/MOD-11).

## MVP Constraints
- Attendance statuses: `present`, `late`, `absent`, `early_leave`.
- Uniqueness constraint: `(student_id, schedule_id, date)` — enforced at database level.
- Manual entry is faculty/admin-restricted (403 for student role).
- All date/time fields interpreted using configured timezone (`TIMEZONE` env var, default: Asia/Manila for JRMSU pilot).
- Response envelope: `{ "success": true, "data": {}, "message": "" }` for success; `{ "success": false, "error": { "code": "", "message": "" } }` for errors.
- Foreign keys: `student_id` → `users.id`, `schedule_id` → `schedules.id`.

## MVP Gate Criteria
- `FUN-06-01` through `FUN-06-06` implemented and tested.
- Duplicate marking prevention verified (same student/schedule/date returns existing record, not error).
- Manual override and history filters validated.
- Auth enforcement verified: 401 for missing/invalid JWT, 403 for insufficient role on all protected endpoints.
- Timezone configuration validated (date comparisons consistent with TIMEZONE env var).
- Response envelope format consistent across all endpoints.
