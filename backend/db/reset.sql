-- =============================================================================
-- IAMS Database Reset — Wipe all data and reseed
--
-- Usage (from project root):
--   docker compose exec -T postgres psql -U admin -d iams -f /docker-entrypoint-initdb.d/reset.sql
--
-- Or via the helper script:
--   ./scripts/db-reset.sh
-- =============================================================================

-- Disable FK checks during truncate
SET session_replication_role = 'replica';

-- Wipe all data (order doesn't matter with FK checks disabled)
TRUNCATE TABLE
    refresh_tokens,
    presence_logs,
    early_leave_events,
    attendance_records,
    enrollments,
    schedules,
    face_embeddings,
    face_registrations,
    notifications,
    notification_preferences,
    rooms,
    users,
    student_records,
    faculty_records,
    system_settings
CASCADE;

-- Re-enable FK checks
SET session_replication_role = 'origin';

-- Now reseed
\i /docker-entrypoint-initdb.d/02-seed.sql

-- Verify
SELECT 'Reset complete. Seed data:' AS status;
SELECT 'users: ' || count(*) FROM users
UNION ALL SELECT 'faculty_records: ' || count(*) FROM faculty_records
UNION ALL SELECT 'student_records: ' || count(*) FROM student_records
UNION ALL SELECT 'rooms: ' || count(*) FROM rooms
UNION ALL SELECT 'schedules: ' || count(*) FROM schedules
UNION ALL SELECT 'enrollments: ' || count(*) FROM enrollments
UNION ALL SELECT 'system_settings: ' || count(*) FROM system_settings;
