# Database Specialist Memory

## Supabase Project Details
- **Project Ref:** fspnxqmewtxmuyqqwwni
- **Region:** aws-1-ap-southeast-2 (AWS Sydney, AU)
- **PostgreSQL Version:** 17.6 on aarch64-unknown-linux-gnu
- **DB Host (direct, IPv6 only):** db.fspnxqmewtxmuyqqwwni.supabase.co (AAAA: 2406:da1c:f42:ae00:6b9d:156:9d29:865b)
- **DB Host (pooler, IPv4):** aws-1-ap-southeast-2.pooler.supabase.com
- **Pooler Ports:** 5432 (session mode), 6543 (transaction mode)
- **Pooler User Format:** postgres.fspnxqmewtxmuyqqwwni

## Connection Notes
- See [supabase-connection.md](supabase-connection.md) for detailed connection troubleshooting notes

## Schema State
- **Migration head:** e49171084f7c (Initial schema - create 8 tables)
- **Tables (8+1):** users, face_registrations, rooms, schedules, enrollments, attendance_records, presence_logs, early_leave_events, alembic_version
- **Enums:** userrole (STUDENT, FACULTY, ADMIN), attendancestatus (PRESENT, LATE, ABSENT, EARLY_LEAVE)
- All tables use UUID primary keys (no default gen_random_uuid -- UUIDs must be generated app-side)
- presence_logs uses BIGSERIAL for id (auto-incrementing, high-volume table)

## Key Indexes
- users: unique on email, unique on student_id, index on role
- face_registrations: unique on user_id, index on is_active
- schedules: composite (day_of_week, start_time), faculty_id, room_id, subject_code
- attendance_records: unique constraint (student_id, schedule_id, date), date, schedule_id, student_id
- enrollments: unique constraint (student_id, schedule_id)

## Foreign Key Relationships
- face_registrations.user_id -> users.id
- schedules.faculty_id -> users.id, schedules.room_id -> rooms.id
- enrollments.student_id -> users.id, enrollments.schedule_id -> schedules.id
- attendance_records.student_id -> users.id, attendance_records.schedule_id -> schedules.id
- early_leave_events.attendance_id -> attendance_records.id
- presence_logs.attendance_id -> attendance_records.id

## Environment Setup
- Backend venv: `C:\.cjjutba\.thesis\iams\backend\venv`
- .env file: `C:\.cjjutba\.thesis\iams\backend\.env`
- Alembic config: `C:\.cjjutba\.thesis\iams\backend\alembic.ini`
- System python can run alembic via `python -m alembic` from backend dir
- Venv python may not execute in sandbox -- use system python with packages installed
