# Glossary

- **Schedule**: Class slot defined by `subject_code`, `subject_name`, `faculty_id` (FK users), `room_id` (FK rooms), `day_of_week` (INTEGER 0-6), `start_time`/`end_time` (TIME type), `semester`, `academic_year`, and `is_active`.
- **Active Schedule**: Schedule with `is_active=true`. Optional `semester`/`academic_year` provide scope context but are not auto-enforced in MVP.
- **Current Class**: Schedule where `is_active=true`, `day_of_week` matches today (0=Sunday, 1=Monday, ..., 6=Saturday), and current time (in configured timezone) falls within `[start_time, end_time]`.
- **Session**: One date-specific instance of a schedule (e.g., "CS101 on 2026-02-12").
- **Enrollment**: Mapping of student to schedule via `enrollments` table. Unique constraint on `(student_id, schedule_id)`.
- **Roster**: Enrolled student list for one schedule, retrieved via `GET /schedules/{id}/students`.
- **Day Filter**: Query filter by `day_of_week` (INTEGER 0-6: 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday).
- **Supabase JWT**: JSON Web Token issued by Supabase Auth, used as `Authorization: Bearer <token>` on all MOD-05 endpoints. Contains `sub` (user ID) and `role` claims.
- **TIME Type**: PostgreSQL TIME type used for `start_time`/`end_time`. Stored without timezone; interpretation uses configured `TIMEZONE` env var.
- **Timezone**: Configured via `TIMEZONE` env var. Default for JRMSU pilot: Asia/Manila (+08:00).
- **Faculty-Schedule Ownership**: Faculty user is linked to schedule via `faculty_id` FK. Faculty can only view their own teaching schedules via `GET /schedules/me`.
- **Enrollment Lifecycle**: In MVP, enrollments are created via MOD-11 import scripts. No direct enrollment API. Enrollments persist when schedule is deactivated (soft delete via `is_active`).
