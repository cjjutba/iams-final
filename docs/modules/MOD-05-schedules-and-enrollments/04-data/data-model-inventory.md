# Data Model Inventory

## Primary Data Stores Used by MOD-05
1. `rooms` — physical classroom locations
2. `schedules` — class schedule records
3. `enrollments` — student-schedule mapping
4. `users` — faculty/student user records (referenced via FK)

## Entities
- **Room**: Physical classroom (id, name, building, capacity, camera_endpoint, is_active).
- **Schedule**: Class slot metadata (id, subject_code, subject_name, faculty_id FK→users, room_id FK→rooms, day_of_week, start_time, end_time, semester, academic_year, is_active).
- **Enrollment**: Student-schedule mapping (id, student_id FK→users, schedule_id FK→schedules, enrolled_at). Unique constraint on `(student_id, schedule_id)`.
- **User**: Faculty and student records (referenced by schedules.faculty_id and enrollments.student_id).

## Ownership
- Schedule/enrollment persistence: backend data layer (SQLAlchemy models, Supabase PostgreSQL).
- CSV import source mapping: `MOD-11` integration.

## Cross-Module Data Flow
- **MOD-04 → MOD-05**: Edge device sends `room_id` → backend looks up schedules for that room → determines "current class" by `day_of_week` and `[start_time, end_time]`.
- **MOD-05 → MOD-06**: Attendance records reference `schedule_id`. Session boundaries derived from `start_time`/`end_time`.
- **MOD-05 → MOD-07**: Presence tracking uses enrolled student list from `enrollments` table and active schedule window for scan intervals.
- **MOD-11 → MOD-05**: Import scripts seed `schedules` and `enrollments` tables from CSV data.

## Enrollment Lifecycle
- **Creation**: Via MOD-11 import scripts or direct DB operations. No API in MVP.
- **Deletion (student removed)**: Cascade-deleted when student is deleted via MOD-02.
- **Schedule deactivation**: When `is_active=false`, enrollments remain in DB for historical records. Active queries filter by `is_active=true`.
- **No soft delete on enrollments**: Enrollments are either present or cascade-deleted. No `is_active` flag on enrollments table.

## MOD-02 User Deletion Impact
When a student is deleted via MOD-02:
- All `enrollments` rows for that `student_id` are cascade-deleted.
- Roster queries (`GET /schedules/{id}/students`) automatically exclude the deleted student.
- Historical `attendance_records` (MOD-06) referencing the student are preserved.
