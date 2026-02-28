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

## Schema State (Updated 2026-02-07)
- **Migration chain:** e49171084f7c (Initial 8 tables) -> 86d63351d3e9 (notifications table) [head]
- **DB stamped at:** 86d63351d3e9 (ALL MIGRATIONS APPLIED, schema sync verified)
- **Tables (9+1):** users, face_registrations, rooms, schedules, enrollments, attendance_records, presence_logs, early_leave_events, notifications, alembic_version
- **Enums:** userrole (STUDENT, FACULTY, ADMIN), attendancestatus (PRESENT, LATE, ABSENT, EARLY_LEAVE)
- All tables use UUID primary keys (no default gen_random_uuid -- UUIDs must be generated app-side)
- presence_logs uses BIGSERIAL for id (auto-incrementing, high-volume table)
- **Migration testing:** Rollback and re-apply tested successfully on 2026-02-07, data preserved

## Key Indexes
- users: unique on email, unique on student_id, index on role
- face_registrations: unique on user_id, index on is_active
- schedules: composite (day_of_week, start_time), faculty_id, room_id, subject_code
- attendance_records: unique constraint (student_id, schedule_id, date), date, schedule_id, student_id
- enrollments: unique constraint (student_id, schedule_id)
- notifications: user_id, type, created_at

## Foreign Key Relationships
- face_registrations.user_id -> users.id
- schedules.faculty_id -> users.id, schedules.room_id -> rooms.id
- enrollments.student_id -> users.id, enrollments.schedule_id -> schedules.id
- attendance_records.student_id -> users.id, attendance_records.schedule_id -> schedules.id
- early_leave_events.attendance_id -> attendance_records.id
- presence_logs.attendance_id -> attendance_records.id
- notifications.user_id -> users.id

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
- Backend venv: `C:\.cjjutba\.thesis\iams\backend\venv`
- .env file: `C:\.cjjutba\.thesis\iams\backend\.env`
- Alembic config: `C:\.cjjutba\.thesis\iams\backend\alembic.ini`
- System python can run alembic via `python -m alembic` from backend dir
- Venv python may not execute in sandbox -- use system python with packages installed

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
