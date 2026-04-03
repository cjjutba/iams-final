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

## Schema State (Updated 2026-03-30)
- **Migration chain:** e49171084f7c -> 86d63351d3e9 -> 64622432db30 -> 53db1ce6f3d0 -> 7bf7e45a61d8 -> a1b2c3d4e5f6 [head] (PENDING: new migration needed for audit fixes)
- **DB stamped at:** a1b2c3d4e5f6 (ALL 6 MIGRATIONS APPLIED, verified 2026-03-01)
- **Model tables (18):** users, face_registrations, face_embeddings, rooms, schedules, enrollments, attendance_records, presence_logs, early_leave_events, notifications, notification_preferences, student_records, faculty_records, refresh_tokens, system_settings, attendance_anomalies, engagement_scores, attendance_predictions + alembic_version
- **Enums:** userrole (STUDENT, FACULTY, ADMIN), attendancestatus (PRESENT, LATE, ABSENT, EARLY_LEAVE, EXCUSED), anomalytype (6 values), risklevel (LOW, MODERATE, HIGH, CRITICAL)
- All tables use UUID primary keys (no default gen_random_uuid -- UUIDs must be generated app-side)
- presence_logs uses BIGSERIAL for id (auto-incrementing, high-volume table)
- student_records PK is student_id (VARCHAR), faculty_records PK is faculty_id (VARCHAR) -- NOT FK'd to users
- schedules has target_course and target_year_level columns (added in a1b2c3d4e5f6)
- users has supabase_user_id, email_verified, email_verified_at columns (added in 53db1ce6f3d0)
- **RLS:** DISABLED on all tables, no policies exist. Access control is application-layer only.
- **Edge Functions:** None deployed
- **Data:** 1 user, 5 enrollments, 5 notifications (minimal test data)
- **Extensions:** uuid-ossp, pgcrypto, pg_stat_statements, pg_graphql, supabase_vault (all Supabase defaults)

## Key Indexes (35 total, verified 2026-03-01)
- users: unique on email, student_id, supabase_user_id; index on role
- face_registrations: unique on user_id, index on is_active
- schedules: composite (day_of_week, start_time), composite (target_course, target_year_level), faculty_id, room_id, subject_code
- attendance_records: unique constraint (student_id, schedule_id, date), date, schedule_id, student_id
- enrollments: unique constraint (student_id, schedule_id), student_id, schedule_id
- notifications: user_id, type, created_at
- student_records: PK on student_id (unique email too)
- faculty_records: PK on faculty_id (unique email too)

## Foreign Key Relationships (CASCADE audit applied 2026-03-30)
- face_registrations.user_id -> users.id (CASCADE)
- schedules.faculty_id -> users.id, schedules.room_id -> rooms.id
- enrollments.student_id -> users.id (CASCADE), enrollments.schedule_id -> schedules.id (CASCADE)
- attendance_records.student_id -> users.id, attendance_records.schedule_id -> schedules.id
- early_leave_events.attendance_id -> attendance_records.id (CASCADE)
- presence_logs.attendance_id -> attendance_records.id (CASCADE)
- notifications.user_id -> users.id (CASCADE)
- engagement_scores.attendance_id -> attendance_records.id (CASCADE)
- attendance_anomalies.student_id -> users.id (CASCADE), schedule_id -> schedules.id (SET NULL)
- attendance_predictions.student_id -> users.id (CASCADE), schedule_id -> schedules.id (CASCADE)

## Constraints (added 2026-03-30)
- rooms: UniqueConstraint("name", "building", name="uq_room_name_building")
- schedules: CheckConstraint("day_of_week >= 0 AND day_of_week <= 6")
- attendance_records: CheckConstraint("presence_score >= 0 AND presence_score <= 100")

## Relationship Pattern (updated 2026-03-30)
- All models now use `back_populates=` (not `backref=`) for bidirectional relationships
- User model has explicit relationships: face_registration, teaching_schedules, enrollments, attendance_records, notifications
- AttendanceRecord has: presence_logs, early_leave_events (both uncommented)
- Schedule has: enrollments, attendance_records (both uncommented)
- Room has: schedules (uncommented)
- Exception: FaceEmbedding still uses `backref=` with cascade on FaceRegistration (intentional for delete-orphan)

## Alembic Notes
- Autogenerate works from sandbox via pooler connection (IPv4)
- Venv python (`backend\venv\Scripts\python.exe`) executes alembic successfully
- env.py loads DATABASE_URL from app.config.settings (Pydantic Settings, .env file)
- env.py must import ALL models for autogenerate to detect new/changed tables
- sqlalchemy.url is NOT set in alembic.ini -- overridden in env.py via config.set_main_option()
- See [migration-process.md](migration-process.md) for detailed migration workflow and best practices

## Scripts Pattern (`backend/scripts/`)
- All scripts use `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` to make `app` importable
- Run via `python -m scripts.<name>` from the `backend/` directory
- Use `SessionLocal()` directly (not `get_db()` generator) for standalone scripts
- Pattern: open session in try, commit on success, rollback on error, close in finally
- Use `argparse` for CLI flags (e.g., `--confirm`, `--dry-run`)
- Supabase admin client: lazy-import inside function so dry-run works without credentials
- `migrate_to_supabase.py`: migrates users without supabase_user_id, sets email_confirm=True, temp passwords

## Environment Setup
- Backend venv (macOS): `/Users/cjjutba/Projects/iams/backend/venv`
- Backend venv (Windows): `C:\.cjjutba\.thesis\iams\backend\venv`
- .env file: `backend/.env` (relative to project root)
- Alembic config: `backend/alembic.ini`
- macOS: use `/Users/cjjutba/Projects/iams/backend/venv/bin/python3` for SQLAlchemy queries
- macOS: no psql installed, but postgresql@17 brew prefix exists at /opt/homebrew/opt/postgresql@17 (bin missing)
- Supabase MCP tools are authenticated to a DIFFERENT account (fiscplus projects) -- use Management API with SUPABASE_ACCESS_TOKEN or SQLAlchemy via pooler for IAMS project queries

## SQLite Test Compatibility (CRITICAL FIX - 2026-02-07)
**Problem:** SQLAlchemy UUID columns fail on SQLite when comparing `Model.id == string_value`
**Root Cause:** SQLite doesn't have native UUID type; SQLAlchemy stores as CHAR(32). Comparison requires UUID object, not string.
**Solution:** Convert ALL string UUID parameters to `uuid.UUID()` before using in SQLAlchemy filters.

**Applied to repositories:**
- `attendance_repository.py` (FIXED): All methods with UUID params now use `uuid.UUID()` conversion
- `face_repository.py` (FIXED): All UUID filter methods converted
- `schedule_repository.py` (FIXED): Reference implementation

**Pattern:**
```python
import uuid  # Add to imports

def get_by_id(self, id: str):
    return self.db.query(Model).filter(Model.id == uuid.UUID(id)).first()
```

**Result:** 45+ test failures eliminated. Tests went from 69 passing to 114 passing.

## BIGSERIAL vs SQLite Autoincrement
**Issue:** `presence_logs.id` uses BIGSERIAL (PostgreSQL), which doesn't map to SQLite autoincrement properly.
**Solution:** Use `Integer().with_variant(BIGINT, "postgresql")` in model definition.
**Implementation:**
```python
from sqlalchemy.dialects.postgresql import BIGINT
id = Column(Integer().with_variant(BIGINT, "postgresql"), primary_key=True, autoincrement=True)
```
**Result:** Allows SQLite tests to use INTEGER PRIMARY KEY AUTOINCREMENT while PostgreSQL production uses BIGSERIAL.
