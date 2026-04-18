-- =============================================================================
-- IAMS Seed Data — Minimal Bootstrap (Docker first-start only)
-- The full dataset is seeded via: python -m scripts.seed_data
-- All INSERTs use ON CONFLICT DO NOTHING for idempotency.
-- =============================================================================

-- ── Faculty Records (HRS mirror) ────────────────────────────────────────────

INSERT INTO faculty_records (faculty_id, first_name, last_name, email, department, is_active)
VALUES
    ('FAC-001', 'Faculty', 'EB226', 'faculty.eb226@gmail.com', 'Computer Engineering', TRUE),
    ('FAC-002', 'Faculty', 'EB227', 'faculty.eb227@gmail.com', 'Computer Engineering', TRUE)
ON CONFLICT DO NOTHING;

-- ── Faculty User Accounts ───────────────────────────────────────────────────
-- password: password123
-- bcrypt hash: $2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK

INSERT INTO users (id, email, password_hash, role, first_name, last_name, email_verified, is_active)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'faculty.eb226@gmail.com',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'FACULTY', 'Faculty', 'EB226', TRUE, TRUE),
    ('00000000-0000-0000-0000-000000000002', 'faculty.eb227@gmail.com',
     '$2b$12$rXqVEONjSmvmT9xpOuUa0ehG7BTZpYZqCBJtacIwROmfixCTcFONK',
     'FACULTY', 'Faculty', 'EB227', TRUE, TRUE),
    ('00000000-0000-0000-0000-000000000003', 'admin@admin.com',
     '$2b$12$d/omfPZz504NVs.iyGPYzOiVPMnG1AcxEbPtdhC6obDuDsXdxeQXO',
     'ADMIN', 'System', 'Admin', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- ── Rooms ───────────────────────────────────────────────────────────────────

INSERT INTO rooms (id, name, building, capacity, camera_endpoint, stream_key, is_active)
VALUES
    ('00000000-0000-0000-0000-000000000101', 'EB226', 'Engineering Building', 50,
     'rtsp://mediamtx:8554/eb226', 'eb226', TRUE),
    ('00000000-0000-0000-0000-000000000102', 'EB227', 'Engineering Building', 50,
     'rtsp://mediamtx:8554/eb227', 'eb227', TRUE)
ON CONFLICT DO NOTHING;

-- ── Schedules ───────────────────────────────────────────────────────────────
-- Test schedules (rolling 30-min sessions for EB226 and EB227) and real
-- course schedules are now inserted exclusively by `scripts.seed_data`.
-- This file intentionally leaves the schedules table empty at first-init so
-- the Python seed is the single source of truth.

-- ── System Settings ─────────────────────────────────────────────────────────

INSERT INTO system_settings (id, key, value)
VALUES
    ('00000000-0000-0000-0000-000000000901', 'scan_interval_seconds', '15'),
    ('00000000-0000-0000-0000-000000000902', 'early_leave_threshold', '3'),
    ('00000000-0000-0000-0000-000000000903', 'grace_period_minutes', '15'),
    ('00000000-0000-0000-0000-000000000904', 'recognition_threshold', '0.45'),
    ('00000000-0000-0000-0000-000000000905', 'session_buffer_minutes', '5'),
    ('00000000-0000-0000-0000-000000000906', 'academic_year', '2025-2026'),
    ('00000000-0000-0000-0000-000000000907', 'semester', '2nd')
ON CONFLICT DO NOTHING;
