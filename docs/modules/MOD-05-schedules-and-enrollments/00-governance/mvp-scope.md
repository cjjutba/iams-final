# MVP Scope

## In Scope
- List schedules by day/filter (`GET /api/v1/schedules?day=1`), Supabase JWT required.
- Get one schedule by ID (`GET /api/v1/schedules/{id}`), Supabase JWT required.
- Create schedule (`POST /api/v1/schedules`), admin-only via Supabase JWT role check.
- Get schedules for current user (`GET /api/v1/schedules/me`), role-scoped: faculty by `faculty_id`, student by enrollments.
- Get students enrolled in a schedule (`GET /api/v1/schedules/{id}/students`), restricted to faculty/admin/enrolled students.
- Timezone-aware time comparisons using configured timezone (Asia/Manila for JRMSU pilot).

## Out of Scope
- Full admin UI for schedule maintenance (future enhancement).
- Automatic schedule conflict optimization.
- Semester planner automation.
- Direct enrollment creation/deletion API (enrollments seeded via MOD-11 import scripts for MVP).
- Automatic schedule deactivation based on academic calendar (manual `is_active` toggle for MVP).
- Rate limiting (thesis demonstration).

## MVP Constraints
- Schedule uses `day_of_week` (INTEGER 0-6: 0=Sunday, 1=Monday, ..., 6=Saturday), `start_time`/`end_time` (TIME type), and `is_active` (BOOLEAN, DEFAULT true).
- Enrollment uses unique constraint `(student_id, schedule_id)`.
- All time comparisons use consistent timezone (configured via `TIMEZONE` env var, default: Asia/Manila).
- Auth: Supabase JWT for all endpoints; admin role required for schedule creation.
- Response envelope: `{ "success": true, "data": {}, "message": "" }`.

## MVP Gate Criteria
- `FUN-05-01` through `FUN-05-05` implemented and tested.
- Role-aware schedule retrieval works for student/faculty with Supabase JWT.
- Enrollment lookups match roster data with access control enforced.
- Admin-only schedule creation verified (non-admin returns 403).
- Missing/invalid token returns 401 on all protected endpoints.
- Timezone configuration documented and applied consistently.
