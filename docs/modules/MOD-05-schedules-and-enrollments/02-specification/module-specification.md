# Module Specification

## Module ID
`MOD-05`

## Purpose
Define class schedules and enroll students per class. Provide schedule context for downstream attendance (MOD-06), presence tracking (MOD-07), and edge device pipeline (MOD-04).

## Auth Context
All endpoints require Supabase JWT (`Authorization: Bearer <token>`). Schedule creation is admin-only (`role == "admin"`). Role-scoped queries use JWT `sub` (user ID) and `role` claims.

## Core Functions
- `FUN-05-01`: List schedules by filters/day (Supabase JWT, all roles).
- `FUN-05-02`: Get schedule by ID (Supabase JWT, all roles).
- `FUN-05-03`: Create schedule (Supabase JWT, admin-only).
- `FUN-05-04`: Get schedules for current user (Supabase JWT, role-scoped).
- `FUN-05-05`: Get students assigned to schedule (Supabase JWT, restricted access).

## API Contracts
- `GET /api/v1/schedules?day=1` — list with filters
- `GET /api/v1/schedules/{id}` — get by ID
- `POST /api/v1/schedules` — create (admin)
- `GET /api/v1/schedules/me` — current user schedules
- `GET /api/v1/schedules/{id}/students` — enrolled roster

## Data Dependencies
- `rooms` — classroom locations (FK from schedules)
- `schedules` — class schedule records
- `enrollments` — student-schedule mapping (unique constraint on `student_id, schedule_id`)
- `users` — faculty/student user records (FK from schedules and enrollments)

## Screen Dependencies
- `SCR-012` StudentScheduleScreen
- `SCR-020` FacultyScheduleScreen

## Cross-Module Coordination
- **MOD-04** (Edge Device): Edge sends `room_id` in `/face/process` payload; backend uses rooms→schedules mapping to infer active schedule context for attendance.
- **MOD-06** (Attendance): Uses `schedule_id` and timing semantics to create/update attendance records. Depends on schedule `start_time`/`end_time` for session boundaries.
- **MOD-07** (Presence Tracking): Uses enrolled students list and active schedule to compute presence scores during 60-second scan intervals.
- **MOD-11** (Data Import): Seeds schedules and enrollments from CSV. No direct enrollment API in MVP.
- **MOD-02** (User Management): When a student is deleted, enrollments for that student are cascade-deleted.

## Enrollment Scope Note
MOD-05 MVP does NOT provide a direct API to create/modify enrollments. Enrollments are seeded and managed by:
1. MOD-11 data import scripts (bulk load from CSV).
2. Direct database operations by admin (future: via admin dashboard).
Future enhancements may add `POST /enrollments` and `DELETE /enrollments/{id}`.

## Done Criteria
- Time/day filters return correct active schedules with deterministic ordering.
- Enrollment relationships are enforced by DB unique constraint.
- Schedule ownership and permissions are validated via Supabase JWT.
- Admin-only schedule creation returns 403 for non-admin callers.
- Missing/invalid JWT returns 401 on all endpoints.
- Timezone configuration is applied consistently to time comparisons.
- Roster access control is enforced (faculty/admin/enrolled students only).
