-- =============================================================================
-- IAMS Database Schema
-- Matches SQLAlchemy models in backend/app/models/
-- =============================================================================

-- ── Enum Types ───────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE userrole AS ENUM ('STUDENT', 'FACULTY', 'ADMIN');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE attendancestatus AS ENUM ('PRESENT', 'LATE', 'ABSENT', 'EARLY_LEAVE', 'EXCUSED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Extension ────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Tables ───────────────────────────────────────────────────────────────────

-- users
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255),
    supabase_user_id UUID UNIQUE,
    role            userrole NOT NULL,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    student_id      VARCHAR(50) UNIQUE,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified_at TIMESTAMP,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_supabase_user_id ON users (supabase_user_id);
CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);
CREATE INDEX IF NOT EXISTS ix_users_student_id ON users (student_id);

-- face_registrations
CREATE TABLE IF NOT EXISTS face_registrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL UNIQUE REFERENCES users(id),
    embedding_id    INTEGER NOT NULL,
    embedding_vector BYTEA NOT NULL,
    registered_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_face_registrations_user_id ON face_registrations (user_id);
CREATE INDEX IF NOT EXISTS ix_face_registrations_is_active ON face_registrations (is_active);

-- face_embeddings
CREATE TABLE IF NOT EXISTS face_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    registration_id UUID NOT NULL REFERENCES face_registrations(id) ON DELETE CASCADE,
    faiss_id        INTEGER NOT NULL,
    embedding_vector BYTEA NOT NULL,
    angle_label     VARCHAR(20),
    quality_score   DOUBLE PRECISION,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_face_embeddings_registration_id ON face_embeddings (registration_id);
CREATE INDEX IF NOT EXISTS ix_face_embeddings_faiss_id ON face_embeddings (faiss_id);

-- rooms
CREATE TABLE IF NOT EXISTS rooms (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,
    building        VARCHAR(100) NOT NULL,
    capacity        INTEGER,
    camera_endpoint VARCHAR(255),
    stream_key      VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- schedules
CREATE TABLE IF NOT EXISTS schedules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_code    VARCHAR(20) NOT NULL,
    subject_name    VARCHAR(200) NOT NULL,
    faculty_id      UUID NOT NULL REFERENCES users(id),
    room_id         UUID NOT NULL REFERENCES rooms(id),
    day_of_week     INTEGER NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    semester        VARCHAR(20) NOT NULL,
    academic_year   VARCHAR(20) NOT NULL,
    target_course   VARCHAR(100),
    target_year_level INTEGER,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_schedules_subject_code ON schedules (subject_code);
CREATE INDEX IF NOT EXISTS ix_schedules_faculty_id ON schedules (faculty_id);
CREATE INDEX IF NOT EXISTS ix_schedules_room_id ON schedules (room_id);
CREATE INDEX IF NOT EXISTS idx_schedule_day_time ON schedules (day_of_week, start_time);
CREATE INDEX IF NOT EXISTS idx_schedule_target ON schedules (target_course, target_year_level);

-- enrollments
CREATE TABLE IF NOT EXISTS enrollments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES users(id),
    schedule_id     UUID NOT NULL REFERENCES schedules(id),
    enrolled_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_student_schedule UNIQUE (student_id, schedule_id)
);

CREATE INDEX IF NOT EXISTS ix_enrollments_student_id ON enrollments (student_id);
CREATE INDEX IF NOT EXISTS ix_enrollments_schedule_id ON enrollments (schedule_id);

-- attendance_records
CREATE TABLE IF NOT EXISTS attendance_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES users(id),
    schedule_id     UUID NOT NULL REFERENCES schedules(id),
    date            DATE NOT NULL DEFAULT CURRENT_DATE,
    status          attendancestatus NOT NULL DEFAULT 'ABSENT',
    check_in_time   TIMESTAMP,
    check_out_time  TIMESTAMP,
    presence_score  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_scans     INTEGER NOT NULL DEFAULT 0,
    scans_present   INTEGER NOT NULL DEFAULT 0,
    total_present_seconds DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    remarks         TEXT,
    CONSTRAINT uq_student_schedule_date UNIQUE (student_id, schedule_id, date)
);

CREATE INDEX IF NOT EXISTS ix_attendance_records_student_id ON attendance_records (student_id);
CREATE INDEX IF NOT EXISTS ix_attendance_records_schedule_id ON attendance_records (schedule_id);
CREATE INDEX IF NOT EXISTS ix_attendance_records_date ON attendance_records (date);

-- presence_logs
CREATE TABLE IF NOT EXISTS presence_logs (
    id              BIGSERIAL PRIMARY KEY,
    attendance_id   UUID NOT NULL REFERENCES attendance_records(id),
    scan_number     INTEGER NOT NULL,
    scan_time       TIMESTAMP NOT NULL DEFAULT NOW(),
    detected        BOOLEAN NOT NULL,
    confidence      DOUBLE PRECISION,
    track_id        INTEGER
);

CREATE INDEX IF NOT EXISTS ix_presence_logs_attendance_id ON presence_logs (attendance_id);

-- early_leave_events
CREATE TABLE IF NOT EXISTS early_leave_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attendance_id   UUID NOT NULL REFERENCES attendance_records(id),
    detected_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMP NOT NULL,
    consecutive_misses INTEGER NOT NULL,
    notified        BOOLEAN NOT NULL DEFAULT FALSE,
    notified_at     TIMESTAMP,
    returned        BOOLEAN NOT NULL DEFAULT FALSE,
    returned_at     TIMESTAMP,
    absence_duration_seconds INTEGER,
    context_severity VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS ix_early_leave_events_attendance_id ON early_leave_events (attendance_id);

-- notifications
CREATE TABLE IF NOT EXISTS notifications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),
    title           VARCHAR(255) NOT NULL,
    message         TEXT NOT NULL,
    type            VARCHAR(50) NOT NULL DEFAULT 'system',
    read            BOOLEAN NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMP,
    reference_id    VARCHAR(255),
    reference_type  VARCHAR(50),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_type ON notifications (type);
CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at);

-- notification_preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id                 UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    early_leave_alerts      BOOLEAN NOT NULL DEFAULT TRUE,
    anomaly_alerts          BOOLEAN NOT NULL DEFAULT TRUE,
    attendance_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    low_attendance_warning  BOOLEAN NOT NULL DEFAULT TRUE,
    daily_digest            BOOLEAN NOT NULL DEFAULT FALSE,
    weekly_digest           BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
    low_attendance_threshold DOUBLE PRECISION NOT NULL DEFAULT 75.0
);

-- student_records (SIS mirror)
CREATE TABLE IF NOT EXISTS student_records (
    student_id      VARCHAR(50) PRIMARY KEY,
    first_name      VARCHAR(100) NOT NULL,
    middle_name     VARCHAR(100),
    last_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(255),
    course          VARCHAR(100),
    year_level      INTEGER,
    section         VARCHAR(10),
    birthdate       DATE,
    contact_number  VARCHAR(20),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- faculty_records (HRS mirror)
CREATE TABLE IF NOT EXISTS faculty_records (
    faculty_id      VARCHAR(50) PRIMARY KEY,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    department      VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- system_settings
CREATE TABLE IF NOT EXISTS system_settings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key             VARCHAR(100) NOT NULL UNIQUE,
    value           TEXT NOT NULL,
    updated_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_system_settings_key ON system_settings (key);

-- refresh_tokens (JWT token rotation)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,
    expires_at      TIMESTAMP NOT NULL,
    revoked         BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at      TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    replaced_by     UUID REFERENCES refresh_tokens(id)
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON refresh_tokens (expires_at);
