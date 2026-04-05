# Full Local Docker Stack — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the entire IAMS system off Supabase to a fully self-contained Docker stack with local PostgreSQL, local JWT auth, and near real-time face recognition — deployable to DigitalOcean VPS.

**Architecture:** 7-service Docker Compose stack (PostgreSQL, Redis, mediamtx, coturn, FastAPI backend, Dozzle, Adminer for dev). Backend uses ByteTrack + cached ArcFace for near real-time recognition. Local JWT auth replaces Supabase Auth. Same stack deploys to 4vCPU/8GB VPS.

**Tech Stack:** FastAPI, PostgreSQL 16, Redis 7, mediamtx, coturn, InsightFace (SCRFD+ArcFace), FAISS, ByteTrack, python-jose, bcrypt, Kotlin/Jetpack Compose, ExoPlayer, ML Kit, CameraX

**Design Doc:** `docs/plans/2026-03-23-full-local-docker-stack-design.md`

---

## Phase 1: Docker Infrastructure

### Task 1: Add PostgreSQL to Docker Compose

**Files:**
- Modify: `docker-compose.yml`
- Create: `backend/db/init.sql`
- Create: `backend/db/seed.sql`

**Step 1: Create the database init directory**

Run: `mkdir -p backend/db`

**Step 2: Write the init.sql schema**

Create `backend/db/init.sql` with all tables matching the existing SQLAlchemy models. This runs once on first `docker compose up`:

```sql
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    student_id VARCHAR(50) UNIQUE,
    email_verified BOOLEAN DEFAULT TRUE,
    email_verified_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_student_id ON users(student_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================================
-- STUDENT RECORDS (SIS mirror)
-- ============================================================
CREATE TABLE IF NOT EXISTS student_records (
    student_id VARCHAR(50) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    course VARCHAR(100),
    year_level INTEGER,
    section VARCHAR(20),
    birthdate DATE,
    contact_number VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- FACULTY RECORDS (HRS mirror)
-- ============================================================
CREATE TABLE IF NOT EXISTS faculty_records (
    faculty_id VARCHAR(50) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- FACE REGISTRATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS face_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    embedding_id INTEGER,
    embedding_vector BYTEA,
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- FACE EMBEDDINGS (multi-angle)
-- ============================================================
CREATE TABLE IF NOT EXISTS face_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id UUID REFERENCES face_registrations(id) ON DELETE CASCADE,
    faiss_id INTEGER,
    embedding_vector BYTEA,
    angle_label VARCHAR(20),
    quality_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_face_embeddings_registration_id ON face_embeddings(registration_id);
CREATE INDEX IF NOT EXISTS ix_face_embeddings_faiss_id ON face_embeddings(faiss_id);

-- ============================================================
-- ROOMS
-- ============================================================
CREATE TABLE IF NOT EXISTS rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    building VARCHAR(100),
    capacity INTEGER,
    camera_endpoint VARCHAR(255),
    stream_key VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- SCHEDULES
-- ============================================================
CREATE TABLE IF NOT EXISTS schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_code VARCHAR(20),
    subject_name VARCHAR(200) NOT NULL,
    faculty_id UUID REFERENCES users(id),
    room_id UUID REFERENCES rooms(id),
    day_of_week INTEGER NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    semester VARCHAR(20),
    academic_year VARCHAR(20),
    target_course VARCHAR(100),
    target_year_level INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_schedule_day_time ON schedules(day_of_week, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_schedule_target ON schedules(target_course, target_year_level);

-- ============================================================
-- ENROLLMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES users(id) ON DELETE CASCADE,
    schedule_id UUID REFERENCES schedules(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_student_schedule UNIQUE (student_id, schedule_id)
);

-- ============================================================
-- ATTENDANCE RECORDS
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES users(id),
    schedule_id UUID REFERENCES schedules(id),
    date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'absent',
    check_in_time TIMESTAMPTZ,
    check_out_time TIMESTAMPTZ,
    presence_score FLOAT DEFAULT 0.0,
    total_scans INTEGER DEFAULT 0,
    scans_present INTEGER DEFAULT 0,
    total_present_seconds FLOAT DEFAULT 0.0,
    remarks TEXT,
    CONSTRAINT uq_student_schedule_date UNIQUE (student_id, schedule_id, date)
);

-- ============================================================
-- PRESENCE LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS presence_logs (
    id BIGSERIAL PRIMARY KEY,
    attendance_id UUID REFERENCES attendance_records(id) ON DELETE CASCADE,
    scan_number INTEGER,
    scan_time TIMESTAMPTZ,
    detected BOOLEAN DEFAULT FALSE,
    confidence FLOAT,
    track_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_presence_logs_attendance ON presence_logs(attendance_id);

-- ============================================================
-- EARLY LEAVE EVENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS early_leave_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_id UUID REFERENCES attendance_records(id) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ,
    consecutive_misses INTEGER DEFAULT 0,
    notified BOOLEAN DEFAULT FALSE,
    notified_at TIMESTAMPTZ,
    returned BOOLEAN DEFAULT FALSE,
    returned_at TIMESTAMPTZ,
    absence_duration_seconds FLOAT,
    context_severity VARCHAR(20)
);

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    type VARCHAR(50),
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    reference_id UUID,
    reference_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at);

-- ============================================================
-- NOTIFICATION PREFERENCES
-- ============================================================
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    early_leave_alerts BOOLEAN DEFAULT TRUE,
    anomaly_alerts BOOLEAN DEFAULT TRUE,
    attendance_confirmation BOOLEAN DEFAULT TRUE,
    low_attendance_warning BOOLEAN DEFAULT TRUE,
    daily_digest BOOLEAN DEFAULT FALSE,
    weekly_digest BOOLEAN DEFAULT FALSE,
    email_enabled BOOLEAN DEFAULT FALSE,
    low_attendance_threshold FLOAT DEFAULT 75.0
);

-- ============================================================
-- SYSTEM SETTINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- REFRESH TOKENS (new for local JWT auth)
-- ============================================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
```

**Step 3: Write the seed.sql file**

Create `backend/db/seed.sql` — this seeds faculty accounts, rooms, schedules, test students, and enrollments. Passwords are bcrypt-hashed (the hash below is for password `"password123"`):

```sql
-- ============================================================
-- SEED DATA — runs on first docker compose up
-- ============================================================

-- Faculty accounts (password: "password123")
-- bcrypt hash: $2b$12$LJ3m4ys3Lk0TSwHBQf2wAOmFGaN7EKMqaOXJGaLGBsFAzzCBXkeqy
INSERT INTO users (id, email, password_hash, first_name, last_name, role, student_id) VALUES
    ('00000000-0000-0000-0000-000000000001', 'faculty1@jrmsu.edu.ph', '$2b$12$LJ3m4ys3Lk0TSwHBQf2wAOmFGaN7EKMqaOXJGaLGBsFAzzCBXkeqy', 'Juan', 'Dela Cruz', 'faculty', NULL),
    ('00000000-0000-0000-0000-000000000002', 'faculty2@jrmsu.edu.ph', '$2b$12$LJ3m4ys3Lk0TSwHBQf2wAOmFGaN7EKMqaOXJGaLGBsFAzzCBXkeqy', 'Maria', 'Santos', 'faculty', NULL)
ON CONFLICT (email) DO NOTHING;

-- Faculty records (HRS mirror)
INSERT INTO faculty_records (faculty_id, first_name, last_name, email, department) VALUES
    ('FAC-001', 'Juan', 'Dela Cruz', 'faculty1@jrmsu.edu.ph', 'Computer Science'),
    ('FAC-002', 'Maria', 'Santos', 'faculty2@jrmsu.edu.ph', 'Information Technology')
ON CONFLICT (faculty_id) DO NOTHING;

-- Rooms
INSERT INTO rooms (id, name, building, capacity, camera_endpoint, stream_key) VALUES
    ('00000000-0000-0000-0000-000000000101', 'Room 101', 'Main Building', 40, 'rtsp://mediamtx:8554/room101/raw', 'room101'),
    ('00000000-0000-0000-0000-000000000102', 'Room 102', 'Main Building', 35, 'rtsp://mediamtx:8554/room102/raw', 'room102')
ON CONFLICT (id) DO NOTHING;

-- Student records (SIS mirror — for student ID verification during registration)
INSERT INTO student_records (student_id, first_name, middle_name, last_name, email, course, year_level, section, birthdate) VALUES
    ('STU-2024-001', 'Pedro', 'Garcia', 'Reyes', 'pedro.reyes@jrmsu.edu.ph', 'BSCS', 3, 'A', '2003-05-15'),
    ('STU-2024-002', 'Ana', 'Lopez', 'Torres', 'ana.torres@jrmsu.edu.ph', 'BSIT', 2, 'B', '2004-02-20'),
    ('STU-2024-003', 'Carlos', NULL, 'Mendoza', 'carlos.mendoza@jrmsu.edu.ph', 'BSCS', 3, 'A', '2003-08-10'),
    ('STU-2024-004', 'Sofia', 'Cruz', 'Ramos', 'sofia.ramos@jrmsu.edu.ph', 'BSIT', 2, 'B', '2004-11-03'),
    ('STU-2024-005', 'Miguel', NULL, 'Santos', 'miguel.santos@jrmsu.edu.ph', 'BSCS', 4, 'A', '2002-01-25')
ON CONFLICT (student_id) DO NOTHING;

-- Test student accounts (pre-registered, password: "password123")
INSERT INTO users (id, email, password_hash, first_name, last_name, role, student_id) VALUES
    ('00000000-0000-0000-0000-000000000201', 'pedro.reyes@jrmsu.edu.ph', '$2b$12$LJ3m4ys3Lk0TSwHBQf2wAOmFGaN7EKMqaOXJGaLGBsFAzzCBXkeqy', 'Pedro', 'Reyes', 'student', 'STU-2024-001'),
    ('00000000-0000-0000-0000-000000000202', 'ana.torres@jrmsu.edu.ph', '$2b$12$LJ3m4ys3Lk0TSwHBQf2wAOmFGaN7EKMqaOXJGaLGBsFAzzCBXkeqy', 'Ana', 'Torres', 'student', 'STU-2024-002')
ON CONFLICT (email) DO NOTHING;

-- Schedules (MWF and TTh classes)
INSERT INTO schedules (id, subject_code, subject_name, faculty_id, room_id, day_of_week, start_time, end_time, semester, academic_year, target_course, target_year_level) VALUES
    -- Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4
    ('00000000-0000-0000-0000-000000000301', 'CS301', 'Data Structures', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 0, '08:00', '09:30', '2nd', '2025-2026', 'BSCS', 3),
    ('00000000-0000-0000-0000-000000000302', 'CS301', 'Data Structures', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 2, '08:00', '09:30', '2nd', '2025-2026', 'BSCS', 3),
    ('00000000-0000-0000-0000-000000000303', 'IT201', 'Web Development', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000102', 1, '10:00', '11:30', '2nd', '2025-2026', 'BSIT', 2),
    ('00000000-0000-0000-0000-000000000304', 'IT201', 'Web Development', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000102', 3, '10:00', '11:30', '2nd', '2025-2026', 'BSIT', 2)
ON CONFLICT (id) DO NOTHING;

-- Enrollments (test students enrolled in classes)
INSERT INTO enrollments (id, student_id, schedule_id) VALUES
    ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000301'),
    ('00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000302'),
    ('00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000303'),
    ('00000000-0000-0000-0000-000000000404', '00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000304')
ON CONFLICT (id) DO NOTHING;

-- System settings
INSERT INTO system_settings (key, value) VALUES
    ('recognition_threshold', '0.30'),
    ('scan_interval_seconds', '15'),
    ('early_leave_threshold', '3'),
    ('processing_fps', '10.0')
ON CONFLICT (key) DO NOTHING;
```

**Step 4: Update docker-compose.yml**

Add postgres, coturn, dozzle, adminer services. Update api-gateway to depend on postgres:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: iams
      POSTGRES_USER: iams
      POSTGRES_PASSWORD: iams_dev_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/01-init.sql
      - ./backend/db/seed.sql:/docker-entrypoint-initdb.d/02-seed.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U iams -d iams"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru --save ""
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  mediamtx:
    image: bluenviron/mediamtx:latest
    ports:
      - "8554:8554"
      - "8887:8887/udp"
      - "8889:8889"
    volumes:
      - ./deploy/mediamtx.dev.yml:/mediamtx.yml
    restart: unless-stopped

  coturn:
    image: coturn/coturn:latest
    ports:
      - "3478:3478"
      - "3478:3478/udp"
    command: >
      -n --log-file=stdout
      --realm=iams
      --fingerprint
      --lt-cred-mech
      --user=iams:iams-turn-secret
      --no-tls --no-dtls
    restart: unless-stopped

  api-gateway:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./backend:/app
      - faiss_data:/app/data/faiss
      - face_uploads:/app/data/uploads/faces
    command: >
      uvicorn app.main:app
      --host 0.0.0.0 --port 8000
      --reload --reload-dir /app/app
      --workers 1
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped

  dozzle:
    image: amir20/dozzle:latest
    ports:
      - "9999:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped

  adminer:
    image: adminer:latest
    ports:
      - "8080:8080"
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
  faiss_data:
  face_uploads:
```

**Step 5: Update backend/.env for local PostgreSQL**

Replace the Supabase DATABASE_URL and remove Supabase vars:

```env
# Database (local Docker PostgreSQL)
DATABASE_URL=postgresql://iams:iams_dev_password@postgres:5432/iams

# Auth (local JWT)
SECRET_KEY=dev-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis
REDIS_URL=redis://redis:6379/0

# ML
RECOGNITION_THRESHOLD=0.30
FAISS_INDEX_PATH=data/faiss/faces.index
PROCESSING_FPS=10.0
WS_BROADCAST_FPS=10.0
RECOGNITION_FPS=15.0

# Presence tracking
SCAN_INTERVAL_SECONDS=15
EARLY_LEAVE_THRESHOLD=3
PRESENCE_FLUSH_INTERVAL=60

# Streaming
DETECTION_SOURCE=composited
CAMERA_SOURCE=mediamtx
USE_WEBRTC_STREAMING=true
MEDIAMTX_EXTERNAL=false
MEDIAMTX_API_URL=http://mediamtx:9997
MEDIAMTX_RTSP_URL=rtsp://mediamtx:8554

# Debug
DEBUG=true
LOG_LEVEL=INFO
```

**Step 6: Test the Docker stack**

Run: `docker compose down -v && docker compose up -d`
Expected: All 7 services start, postgres creates tables and seeds data.

Run: `docker compose logs postgres | grep "database system is ready"`
Expected: PostgreSQL ready message.

Run: `docker compose exec postgres psql -U iams -d iams -c "SELECT email, role FROM users;"`
Expected: Faculty and test student accounts listed.

**Step 7: Commit**

```bash
git add backend/db/init.sql backend/db/seed.sql docker-compose.yml backend/.env
git commit -m "feat: add PostgreSQL, coturn, dozzle, adminer to Docker stack

Replace Supabase Cloud DB with local Docker PostgreSQL.
Add init.sql schema and seed.sql test data.
Add coturn for WebRTC NAT traversal.
Add Dozzle for log viewing and Adminer for DB browsing."
```

---

## Phase 2: Remove Supabase Auth — Backend

### Task 2: Clean up config.py — remove Supabase settings

**Files:**
- Modify: `backend/app/config.py` (lines 23-29, 39)

**Step 1: Remove Supabase config vars**

In `backend/app/config.py`, remove these lines:
- `SUPABASE_URL` (line 23)
- `SUPABASE_ANON_KEY` (line 24)
- `SUPABASE_SERVICE_KEY` (line 25)
- `SUPABASE_JWT_SECRET` (line 26)
- `SUPABASE_WEBHOOK_SECRET` (line 27)
- `SUPABASE_ACCESS_TOKEN` (line 28-29)
- `USE_SUPABASE_AUTH` (line 39)

Keep all JWT settings (`SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`) — they're already there.

**Step 2: Verify the backend still starts**

Run: `docker compose restart api-gateway && docker compose logs -f api-gateway --tail 20`
Expected: FastAPI starts without errors about missing Supabase vars.

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "refactor: remove Supabase config vars from settings"
```

### Task 3: Update User model — remove supabase_user_id, require password_hash

**Files:**
- Modify: `backend/app/models/user.py` (lines 51-52)

**Step 1: Update the User model**

In `backend/app/models/user.py`:
- Line 51: Change `password_hash = Column(String(255), nullable=True)` → `nullable=False`
- Line 52: Remove `supabase_user_id = Column(UUID(as_uuid=True), unique=True, nullable=True, index=True)`

**Step 2: Commit**

```bash
git add backend/app/models/user.py
git commit -m "refactor: remove supabase_user_id, require password_hash in User model"
```

### Task 4: Add RefreshToken model

**Files:**
- Create: `backend/app/models/refresh_token.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the RefreshToken model**

```python
"""RefreshToken model for JWT refresh token rotation."""

from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Step 2: Add to models/__init__.py**

Add `from app.models.refresh_token import RefreshToken` to the imports.

**Step 3: Commit**

```bash
git add backend/app/models/refresh_token.py backend/app/models/__init__.py
git commit -m "feat: add RefreshToken model for JWT token rotation"
```

### Task 5: Clean up security.py — remove Supabase JWT functions

**Files:**
- Modify: `backend/app/utils/security.py` (lines 118-227)

**Step 1: Remove Supabase JWT verification functions**

Delete these functions from `backend/app/utils/security.py`:
- `_fetch_supabase_jwks()` (~lines 118-165)
- `verify_supabase_token()` (~lines 167-210)
- `is_supabase_token()` (~lines 212-227)

Also remove any Supabase-related imports at the top of the file (e.g., `httpx`, `jwcrypto` if only used for Supabase).

Keep all local JWT functions: `hash_password()`, `verify_password()`, `create_access_token()`, `create_refresh_token()`, `verify_token()`, `validate_password_strength()`, `extract_bearer_token()`.

**Step 2: Verify imports**

Run: `docker compose exec api-gateway python -c "from app.utils.security import create_access_token, verify_token, hash_password; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/utils/security.py
git commit -m "refactor: remove Supabase JWT verification from security utils"
```

### Task 6: Simplify dependencies.py — remove dual-auth routing

**Files:**
- Modify: `backend/app/utils/dependencies.py` (lines 20-21, 47-138)

**Step 1: Simplify get_current_user**

Remove:
- Supabase imports (lines 20-21): `from app.utils.security import is_supabase_token, verify_supabase_token`
- Dual-auth routing logic (lines 78-89): the `if is_supabase_token(...)` branch
- Supabase user_id fallback lookup (lines 102-105): `supabase_user_id` query

The simplified `get_current_user` should:
1. Extract Bearer token
2. Call `verify_token()` (local JWT only)
3. Get `sub` (user_id) from payload
4. Query user by `id`
5. Return user or raise 401

**Step 2: Verify the dependency works**

Run: `docker compose restart api-gateway && docker compose logs api-gateway --tail 10`
Expected: No import errors.

**Step 3: Commit**

```bash
git add backend/app/utils/dependencies.py
git commit -m "refactor: simplify get_current_user to local JWT only"
```

### Task 7: Rewrite auth_service.py — remove all Supabase branches

**Files:**
- Modify: `backend/app/services/auth_service.py`

**Step 1: Remove Supabase methods and branches**

Remove:
- `_register_student_supabase()` method (lines 212-316)
- Supabase conditional in `register_student()` (lines 207-208)
- `_verify_supabase_password()` method (lines 402-431)
- Supabase branch in `login()` (lines 385-390)
- Supabase branch in `forgot_password()` (lines 493-520)
- `handle_email_verified()` method (lines 538-570)
- `check_email_verified()` method (lines 572-613)
- `resend_verification_email()` Supabase branch (lines 615-654)
- Supabase password sync in `change_password()` (lines 684-694)

**Step 2: Verify the legacy (local) auth path works**

The existing `_register_student_legacy()` (lines 318-352) becomes the only registration path. It already:
- Validates input
- Hashes password with bcrypt
- Creates user in DB
- Returns JWT tokens

Rename `_register_student_legacy()` to `_register_student()` or just inline it.

**Step 3: Commit**

```bash
git add backend/app/services/auth_service.py
git commit -m "refactor: remove all Supabase auth branches from auth_service"
```

### Task 8: Clean up auth router — remove Supabase endpoints

**Files:**
- Modify: `backend/app/routers/auth.py`

**Step 1: Remove Supabase-only endpoints**

Remove:
- `/resolve-email` endpoint (lines 147-175)
- `/email-confirmed` HTML page endpoint (lines 311-531)
- `/webhook/supabase` endpoint (lines 539-579)

Keep all standard endpoints: `/register`, `/login`, `/refresh`, `/me`, `/change-password`, `/logout`.

**Step 2: Commit**

```bash
git add backend/app/routers/auth.py
git commit -m "refactor: remove Supabase webhook and email confirmation endpoints"
```

### Task 9: Delete supabase_client.py

**Files:**
- Delete: `backend/app/services/supabase_client.py`

**Step 1: Delete the file**

Run: `rm backend/app/services/supabase_client.py`

**Step 2: Search for any remaining imports of supabase_client**

Run: `grep -r "supabase_client" backend/app/`
Expected: No results. If any found, remove those import lines.

**Step 3: Commit**

```bash
git add -u backend/app/services/supabase_client.py
git commit -m "refactor: delete supabase_client.py — no longer needed"
```

### Task 10: Clean up user_service.py — remove Supabase user creation

**Files:**
- Modify: `backend/app/services/user_service.py` (lines 199-201, 293-320)

**Step 1: Remove Supabase code**

- Remove conditional Supabase user creation (lines 199-201)
- Remove `_create_supabase_user()` method (lines 293-320)

**Step 2: Commit**

```bash
git add backend/app/services/user_service.py
git commit -m "refactor: remove Supabase user creation from user_service"
```

### Task 11: Clean up auth schemas — remove SupabaseWebhookPayload

**Files:**
- Modify: `backend/app/schemas/auth.py` (lines 127-134)

**Step 1: Remove the Supabase webhook schema**

Delete `SupabaseWebhookPayload` class (lines 127-134).

**Step 2: Commit**

```bash
git add backend/app/schemas/auth.py
git commit -m "refactor: remove SupabaseWebhookPayload schema"
```

### Task 12: Remove all remaining Supabase references

**Step 1: Search for any remaining Supabase references**

Run: `grep -ri "supabase" backend/app/ --include="*.py" -l`
Expected: No files listed.

If any remain, remove those references.

**Step 2: Search .env files**

Remove any `SUPABASE_*` vars from `backend/.env` and `backend/.env.production`.

**Step 3: Commit**

```bash
git add -A backend/
git commit -m "refactor: remove all remaining Supabase references from backend"
```

---

## Phase 3: Verify Backend Works End-to-End

### Task 13: Start the full stack and test auth flow

**Step 1: Clean start**

Run: `docker compose down -v && docker compose up -d --build`
Expected: All 7 services start.

**Step 2: Wait for health check**

Run: `curl http://localhost:8000/api/v1/health`
Expected: `{"status": "healthy"}` or similar.

**Step 3: Test faculty login**

Run:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "faculty1@jrmsu.edu.ph", "password": "password123"}'
```
Expected: JSON with `access_token`, `refresh_token`, and `user` object.

**Step 4: Test student registration**

Run:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"student_id": "STU-2024-003", "email": "carlos.mendoza@jrmsu.edu.ph", "password": "TestPassword123!", "first_name": "Carlos", "last_name": "Mendoza"}'
```
Expected: JSON with `access_token`, `refresh_token`, and `user` object.

**Step 5: Test protected endpoint**

Use the access_token from step 3:
```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```
Expected: User profile JSON.

**Step 6: Test token refresh**

Use the refresh_token from step 3:
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```
Expected: New `access_token` and `refresh_token`.

**Step 7: Verify database via Adminer**

Open: `http://localhost:8080`
Login: System=PostgreSQL, Server=postgres, Username=iams, Password=iams_dev_password, Database=iams
Check: `users` table has seeded faculty + the registered student.

**Step 8: Verify logs via Dozzle**

Open: `http://localhost:9999`
Check: All containers visible, api-gateway logs show no errors.

**Step 9: Commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: resolve issues from end-to-end auth testing"
```

---

## Phase 4: Update Android App

### Task 14: Update Android auth screens — remove email verification

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegistrationViewModel.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterReviewScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/navigation/IAMSNavHost.kt`

**Step 1: Update RegistrationViewModel**

In `RegistrationViewModel.kt`:
- Remove `checkEmailVerified()` method (lines 217-250)
- Remove `resendVerificationEmail()` method (lines 252-284)
- Remove `startEmailPolling()` / `stopEmailPolling()` methods (lines 286-310)
- Update `register()` to navigate directly to login (or auto-login) instead of email verification

**Step 2: Update RegisterReviewScreen**

In `RegisterReviewScreen.kt`:
- Change the post-registration navigation (lines 78-95): instead of navigating to `EmailVerificationScreen`, navigate to `STUDENT_LOGIN` (or `STUDENT_HOME` if auto-login with tokens)

**Step 3: Update navigation**

In `IAMSNavHost.kt`:
- Remove the `EmailVerificationScreen` route, or keep it as a dead route that redirects to login

**Step 4: Build and verify**

Run: `cd android && ./gradlew assembleDebug`
Expected: Build succeeds.

**Step 5: Commit**

```bash
git add android/
git commit -m "feat(android): remove email verification flow, direct registration to login"
```

### Task 15: Verify Android token refresh interceptor

**Files:**
- Review: `android/app/src/main/java/com/iams/app/data/api/TokenAuthenticator.kt`
- Review: `android/app/src/main/java/com/iams/app/data/api/TokenManager.kt`

**Step 1: Verify TokenAuthenticator**

Read `TokenAuthenticator.kt` — it already handles:
- 401 → call `/api/v1/auth/refresh`
- Save new tokens
- Retry original request

This should work as-is with local JWT auth. No changes expected.

**Step 2: Verify TokenManager**

Read `TokenManager.kt` — it already stores `access_token`, `refresh_token`, `user_role`, `user_id` in DataStore.

No changes expected.

**Step 3: Build**

Run: `cd android && ./gradlew assembleDebug`
Expected: Build succeeds.

**Step 4: Commit (only if changes were needed)**

```bash
git add android/
git commit -m "fix(android): adjust token handling for local JWT auth"
```

---

## Phase 5: Update Production Docker Stack

### Task 16: Update production Docker Compose

**Files:**
- Modify: `deploy/docker-compose.prod.yml`
- Create: `backend/.env.production` (update)

**Step 1: Add postgres, coturn, dozzle to production compose**

Update `deploy/docker-compose.prod.yml` to add:
- `postgres` service (same as dev but with stronger password from env var)
- `coturn` service (same as dev but with production TURN credentials)
- `dozzle` service (same as dev)
- Remove `adminer` (not in production)

Update `api-gateway` to depend on `postgres`.

**Step 2: Update .env.production**

```env
DATABASE_URL=postgresql://iams:STRONG_PROD_PASSWORD@postgres:5432/iams
SECRET_KEY=STRONG_PRODUCTION_SECRET
REDIS_URL=redis://redis:6379/0
RECOGNITION_THRESHOLD=0.45
USE_GPU=false
DEBUG=false
```

Remove all `SUPABASE_*` variables.

**Step 3: Commit**

```bash
git add deploy/docker-compose.prod.yml backend/.env.production
git commit -m "feat: update production Docker stack with PostgreSQL, coturn, dozzle"
```

### Task 17: Update deploy script

**Files:**
- Modify: `deploy/deploy.sh`

**Step 1: Update deploy.sh**

- Add `backend/db/` to rsync (so init.sql and seed.sql are deployed)
- Ensure the deploy script handles the new PostgreSQL volume
- Update firewall rules if needed (port 5432 should NOT be exposed externally)

**Step 2: Commit**

```bash
git add deploy/deploy.sh
git commit -m "feat: update deploy script for new Docker stack"
```

### Task 18: Update dev-up.sh script

**Files:**
- Modify: `scripts/dev-up.sh`

**Step 1: Remove Supabase API calls**

Remove the line that updates Supabase `site_url` via API (around line 40-50 in the current script). Keep the IP detection and mediamtx patching logic.

**Step 2: Commit**

```bash
git add scripts/dev-up.sh
git commit -m "refactor: remove Supabase API call from dev-up.sh"
```

---

## Phase 6: Update database.py for local PostgreSQL

### Task 19: Update database.py connection

**Files:**
- Modify: `backend/app/database.py`

**Step 1: Verify DATABASE_URL defaults**

Ensure `database.py` reads `DATABASE_URL` from environment (it already does). The new `.env` points to `postgresql://iams:iams_dev_password@postgres:5432/iams`.

No code changes should be needed — the connection string change is in `.env`.

**Step 2: Verify connection**

Run: `docker compose restart api-gateway && docker compose logs api-gateway --tail 20`
Expected: Backend connects to local PostgreSQL successfully.

**Step 3: Commit (only if changes needed)**

---

## Phase 7: Final Integration Test

### Task 20: Full end-to-end integration test

**Step 1: Clean start**

```bash
docker compose down -v
docker compose up -d --build
```

**Step 2: Verify all services are healthy**

```bash
docker compose ps
```
Expected: All 7 services running (postgres, redis, mediamtx, coturn, api-gateway, dozzle, adminer).

**Step 3: Test the complete flow**

1. Open Adminer (`http://localhost:8080`) — verify seed data
2. Open Dozzle (`http://localhost:9999`) — verify logs
3. Login as faculty via curl — verify JWT tokens
4. Login as student via curl — verify JWT tokens
5. Register a new student via curl — verify account creation
6. Access protected endpoint with token — verify auth
7. Refresh token — verify rotation

**Step 4: Test with Android app**

1. Update `BACKEND_HOST` in Android build config to point to your Mac's IP
2. Build and install: `cd android && ./gradlew installDebug`
3. Test faculty login
4. Test student registration (skip email verify)
5. Test live feed (if RTSP source available)

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete migration to fully local Docker stack

- PostgreSQL replaces Supabase Cloud DB
- Local JWT auth replaces Supabase Auth
- Added coturn, dozzle, adminer to Docker stack
- All seed data for faculty, rooms, schedules, test students
- Email verification skipped for thesis demo"
```

---

## Summary

| Phase | Tasks | What it does |
|---|---|---|
| **Phase 1** | Task 1 | Docker infrastructure (PostgreSQL, coturn, dozzle, adminer) |
| **Phase 2** | Tasks 2-12 | Remove all Supabase code from backend |
| **Phase 3** | Task 13 | Verify backend auth works end-to-end |
| **Phase 4** | Tasks 14-15 | Update Android app (remove email verify, verify token refresh) |
| **Phase 5** | Tasks 16-18 | Update production stack and deploy scripts |
| **Phase 6** | Task 19 | Verify database connection |
| **Phase 7** | Task 20 | Full integration test |

**Total: 20 tasks across 7 phases.**

## Lessons

- Supabase Auth dual-mode (`USE_SUPABASE_AUTH` flag) created significant code complexity — every auth function had two branches. Removing it simplifies the codebase dramatically.
- The Android app is already JWT-agnostic — `TokenManager`, `AuthInterceptor`, and `TokenAuthenticator` work with any JWT provider. The migration is backend-heavy.
- PostgreSQL init scripts (`/docker-entrypoint-initdb.d/`) only run on first boot when the data volume is empty. Use `docker compose down -v` to wipe and reseed.
- Seed data should use `ON CONFLICT DO NOTHING` to be idempotent — safe to re-run without errors.
- The real-time pipeline (ByteTrack + ArcFace) requires no changes for this migration — it's database and auth agnostic.
