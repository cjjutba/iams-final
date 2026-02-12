# Integration Points

## Backend Integrations
- Schedule router (`backend/app/routers/schedules.py`): REST endpoints with Supabase JWT auth middleware.
- Schedule service (`backend/app/services/schedule_service.py`): Business logic, role-scoped queries.
- Schedule repository (`backend/app/repositories/schedule_repository.py`): Database queries.
- Enrollment repository (`backend/app/repositories/enrollment_repository.py`): Enrollment joins.
- Auth dependency middleware (`backend/app/utils/dependencies.py`): Supabase JWT validation, role extraction.

## Auth Integration
- All endpoints use `get_current_user` dependency (Supabase JWT validation).
- Admin role check via JWT `role` claim for `POST /schedules`.
- Faculty ownership check via `schedule.faculty_id == current_user.id` for roster access.
- Student enrollment check via enrollments table for roster access.

## Mobile Integrations
- Student schedule screen (`mobile/src/screens/student/StudentScheduleScreen.tsx`): calls `GET /api/v1/schedules/me`.
- Faculty schedule screen (`mobile/src/screens/faculty/FacultyScheduleScreen.tsx`): calls `GET /api/v1/schedules/me`.
- Optional class detail views consume `GET /api/v1/schedules/{id}` and `GET /api/v1/schedules/{id}/students`.

## Cross-Module Integrations
- **MOD-04** (Edge Device): Edge sends optional `room_id` in `POST /api/v1/face/process` payload; backend uses `rooms` → `schedules` mapping to infer active schedule context for attendance recording. Backend determines "current class" from `day_of_week` and `[start_time, end_time]` window.
- **MOD-06** (Attendance): Uses `schedule_id` and timing semantics (`start_time`/`end_time`) to determine session boundaries and record attendance.
- **MOD-07** (Presence Tracking): Uses enrolled students list (from `enrollments` table) and active schedule to compute presence scores during 60-second scan intervals. Uses "current class" detection for scan scoping.
- **MOD-11** (Data Import): Seeds `schedules` and `enrollments` tables from CSV data. No direct enrollment API in MVP.
- **MOD-02** (User Management): Student deletion cascades to enrollment deletion. Faculty deletion would orphan schedules (admin must reassign/deactivate).

## Timezone Integration
- All time comparisons use `TIMEZONE` env var (default: Asia/Manila).
- Shared across MOD-05 (schedule windows), MOD-06 (attendance timing), and MOD-07 (presence scan timing).
