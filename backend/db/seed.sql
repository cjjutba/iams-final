-- =============================================================================
-- IAMS Seed Data — Development / Pilot Testing
-- All INSERTs use ON CONFLICT DO NOTHING for idempotency.
-- =============================================================================

-- ── Faculty Records (HRS mirror) ────────────────────────────────────────────

INSERT INTO faculty_records (faculty_id, first_name, last_name, email, department, is_active)
VALUES
    ('FAC-001', 'Maria', 'Santos', 'maria.santos@jrmsu.edu.ph', 'Computer Engineering', TRUE),
    ('FAC-002', 'Jose', 'Reyes', 'jose.reyes@jrmsu.edu.ph', 'Computer Engineering', TRUE),
    ('FAC-003', 'IAMS', 'Faculty', 'faculty@gmail.com', 'Computer Engineering', TRUE)
ON CONFLICT DO NOTHING;

-- ── Faculty User Accounts ───────────────────────────────────────────────────
-- password: password123
-- bcrypt hash: $2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK

INSERT INTO users (id, email, password_hash, role, first_name, last_name, email_verified, is_active)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'maria.santos@jrmsu.edu.ph',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'FACULTY', 'Maria', 'Santos', TRUE, TRUE),
    ('00000000-0000-0000-0000-000000000002', 'jose.reyes@jrmsu.edu.ph',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'FACULTY', 'Jose', 'Reyes', TRUE, TRUE),
    ('00000000-0000-0000-0000-000000000003', 'faculty@gmail.com',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'FACULTY', 'IAMS', 'Faculty', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- ── Rooms ───────────────────────────────────────────────────────────────────

INSERT INTO rooms (id, name, building, capacity, camera_endpoint, stream_key, is_active)
VALUES
    ('00000000-0000-0000-0000-000000000101', 'Room 226', 'Engineering Building', 40,
     'rtsp://mediamtx:8554/eb-226/raw', 'eb-226', TRUE),
    ('00000000-0000-0000-0000-000000000102', 'Room 301', 'Engineering Building', 35,
     'rtsp://mediamtx:8554/eb-301/raw', 'eb-301', TRUE)
ON CONFLICT DO NOTHING;

-- ── Student Records (SIS mirror) ────────────────────────────────────────────

INSERT INTO student_records (student_id, first_name, middle_name, last_name, email, course, year_level, section, birthdate, is_active)
VALUES
    ('21-A-0001', 'Juan', 'Cruz', 'Dela Cruz', 'juan.delacruz@jrmsu.edu.ph', 'BSCPE', 4, 'A', '2002-05-15', TRUE),
    ('21-A-0002', 'Anna', 'Marie', 'Torres', 'anna.torres@jrmsu.edu.ph', 'BSCPE', 4, 'A', '2002-08-22', TRUE),
    ('21-A-0003', 'Pedro', NULL, 'Garcia', 'pedro.garcia@jrmsu.edu.ph', 'BSCPE', 4, 'A', '2001-12-03', TRUE),
    ('21-A-0004', 'Sofia', 'Luz', 'Mendoza', 'sofia.mendoza@jrmsu.edu.ph', 'BSCPE', 4, 'B', '2002-03-10', TRUE),
    ('21-A-0005', 'Carlos', NULL, 'Ramos', 'carlos.ramos@jrmsu.edu.ph', 'BSCPE', 3, 'A', '2003-01-28', TRUE)
ON CONFLICT DO NOTHING;

-- ── Test Student User Accounts ──────────────────────────────────────────────
-- password: password123

INSERT INTO users (id, email, password_hash, role, first_name, last_name, student_id, email_verified, is_active)
VALUES
    ('00000000-0000-0000-0000-000000000011', 'juan.delacruz@jrmsu.edu.ph',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'STUDENT', 'Juan', 'Dela Cruz', '21-A-0001', TRUE, TRUE),
    ('00000000-0000-0000-0000-000000000012', 'anna.torres@jrmsu.edu.ph',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'STUDENT', 'Anna', 'Torres', '21-A-0002', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- ── Schedules ───────────────────────────────────────────────────────────────
-- day_of_week: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri

INSERT INTO schedules (id, subject_code, subject_name, faculty_id, room_id, day_of_week, start_time, end_time, semester, academic_year, target_course, target_year_level, is_active)
VALUES
    -- MWF classes (Prof Santos)
    ('00000000-0000-0000-0000-000000000201', 'CPE301', 'Microprocessors', '00000000-0000-0000-0000-000000000001',
     '00000000-0000-0000-0000-000000000101', 0, '08:00', '09:30', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000202', 'CPE301', 'Microprocessors', '00000000-0000-0000-0000-000000000001',
     '00000000-0000-0000-0000-000000000101', 2, '08:00', '09:30', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    -- TTh classes (Prof Reyes)
    ('00000000-0000-0000-0000-000000000203', 'CPE302', 'Embedded Systems', '00000000-0000-0000-0000-000000000002',
     '00000000-0000-0000-0000-000000000102', 1, '10:00', '11:30', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000204', 'CPE302', 'Embedded Systems', '00000000-0000-0000-0000-000000000002',
     '00000000-0000-0000-0000-000000000102', 3, '10:00', '11:30', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    -- IAMS Test — 24/7 schedule (faculty@gmail.com), one entry per day
    ('00000000-0000-0000-0000-000000000210', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 0, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000211', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 1, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000212', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 2, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000213', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 3, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000214', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 4, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000215', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 5, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE),
    ('00000000-0000-0000-0000-000000000216', 'IAMS', 'IAMS Test', '00000000-0000-0000-0000-000000000003',
     '00000000-0000-0000-0000-000000000101', 6, '00:00', '23:59', '2nd', '2025-2026', 'BSCPE', 4, TRUE)
ON CONFLICT DO NOTHING;

-- ── Enrollments ─────────────────────────────────────────────────────────────
-- Both test students enrolled in all 4 schedule slots

INSERT INTO enrollments (id, student_id, schedule_id)
VALUES
    ('00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000201'),
    ('00000000-0000-0000-0000-000000000302', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000203'),
    ('00000000-0000-0000-0000-000000000303', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000201'),
    ('00000000-0000-0000-0000-000000000304', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000203'),
    -- Test students enrolled in IAMS Test (Mon slot — all days use same enrolled list)
    ('00000000-0000-0000-0000-000000000305', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000210'),
    ('00000000-0000-0000-0000-000000000306', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000210'),
    ('00000000-0000-0000-0000-000000000307', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000211'),
    ('00000000-0000-0000-0000-000000000308', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000211'),
    ('00000000-0000-0000-0000-000000000309', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000212'),
    ('00000000-0000-0000-0000-000000000310', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000212'),
    ('00000000-0000-0000-0000-000000000311', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000213'),
    ('00000000-0000-0000-0000-000000000312', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000213'),
    ('00000000-0000-0000-0000-000000000313', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000214'),
    ('00000000-0000-0000-0000-000000000314', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000214'),
    ('00000000-0000-0000-0000-000000000315', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000215'),
    ('00000000-0000-0000-0000-000000000316', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000215'),
    ('00000000-0000-0000-0000-000000000317', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000216'),
    ('00000000-0000-0000-0000-000000000318', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000216')
ON CONFLICT DO NOTHING;

-- ── System Settings ─────────────────────────────────────────────────────────

INSERT INTO system_settings (id, key, value)
VALUES
    ('00000000-0000-0000-0000-000000000901', 'scan_interval_seconds', '15'),
    ('00000000-0000-0000-0000-000000000902', 'early_leave_threshold', '3'),
    ('00000000-0000-0000-0000-000000000903', 'grace_period_minutes', '15'),
    ('00000000-0000-0000-0000-000000000904', 'recognition_threshold', '0.30'),
    ('00000000-0000-0000-0000-000000000905', 'session_buffer_minutes', '5'),
    ('00000000-0000-0000-0000-000000000906', 'academic_year', '2025-2026'),
    ('00000000-0000-0000-0000-000000000907', 'semester', '2nd')
ON CONFLICT DO NOTHING;
