# Business Rules

## Auth Rules
1. All MOD-05 endpoints require Supabase JWT (`Authorization: Bearer <token>`).
2. Schedule creation (`POST /schedules`) requires `role == "admin"`. Non-admin callers receive 403.
3. Role-scoped queries (`GET /schedules/me`) enforce data boundaries via JWT `sub` and `role`.
4. Roster access (`GET /schedules/{id}/students`) restricted to admin, assigned faculty, or enrolled students.
5. Missing or invalid JWT returns 401 on all endpoints.

## Schedule Rules
1. Schedule is defined by `subject_code`, `subject_name`, `faculty_id` (FK users), `room_id` (FK rooms), `day_of_week` (INTEGER 0-6), `start_time`/`end_time` (TIME type).
2. `start_time` must be strictly earlier than `end_time`.
3. Active schedule uses `is_active=true`. Deactivation is manual toggle (no auto-deactivation in MVP).
4. Optional `semester` (VARCHAR(20)) and `academic_year` (VARCHAR(20)) provide scope context but are not auto-enforced.
5. `day_of_week` mapping: 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday.

## Timezone Rules
1. All time comparisons (`start_time`, `end_time` vs current time) use the configured timezone (`TIMEZONE` env var).
2. `start_time`/`end_time` are stored as TIME type (no timezone info); interpretation assumes configured timezone.
3. For JRMSU pilot: Asia/Manila (+08:00).
4. "Current class" detection: `is_active=true` AND `day_of_week` matches today AND current time (in configured timezone) within `[start_time, end_time]`.

## Enrollment Rules
1. Enrollment must map an existing student (`role == "student"`) to an existing schedule.
2. `(student_id, schedule_id)` must remain unique (DB constraint).
3. Roster lookups return only students with active user accounts.
4. In MVP, enrollments are created via MOD-11 import scripts — no direct enrollment API.
5. When a student is deleted (MOD-02), all enrollments for that student are cascade-deleted.
6. When a schedule is deactivated (`is_active=false`), enrollments remain in DB (preserved for historical records). They are excluded from active queries.

## Access Rules
1. Schedule creation is admin-only in MVP.
2. `GET /schedules/me` returns role-scoped data: faculty sees teaching schedules, student sees enrolled schedules.
3. Roster visibility: admin sees all, faculty sees for own schedules, enrolled students see classmates.
4. Faculty cannot query other faculty members' schedules via `GET /schedules/me`; use `GET /schedules?faculty_id=<id>` for cross-lookup (admin only).

## Integrity Rules
1. Referenced `room_id` and `faculty_id` must exist in their respective tables.
2. `faculty_id` must reference a user with `role == "faculty"`.
3. Schedule retrieval should preserve deterministic ordering by `day_of_week` ASC, `start_time` ASC.
4. API responses should not leak unrelated private data (e.g., student emails in roster are visible to faculty/admin only).
