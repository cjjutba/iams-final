# Business Logic Specialist - Agent Memory

## Project Structure
- Backend root: `C:\.cjjutba\.thesis\iams\backend\`
- Models: `backend/app/models/` - 8 core tables, all use UUID PKs (`UUID(as_uuid=True)`)
- Database: Synchronous SQLAlchemy (`SessionLocal`, `Base`, `engine`) in `backend/app/database.py`
- Security: `backend/app/utils/security.py` - `hash_password()` uses bcrypt via passlib, no validation inside
- Config: `backend/app/config.py` - pydantic-settings `Settings` class, `logger` from `setup_logging()`
- Scripts: `backend/scripts/` - seed data and utility scripts

## Key Model Details
- **User**: UUID PK, `email` (unique), `password_hash`, `role` (UserRole enum: STUDENT/FACULTY/ADMIN), `student_id` (unique, nullable), `is_active`
- **Room**: UUID PK, `name`, `building`, `capacity`, `camera_endpoint`, `is_active`
- **Schedule**: UUID PK, `subject_code`, `subject_name`, `faculty_id` (FK users), `room_id` (FK rooms), `day_of_week` (0=Mon..6=Sun), `start_time`/`end_time` (Time), `semester`, `academic_year`, `is_active`. Has relationship to User via `faculty` and Room via `room`.
- **Enrollment**: UUID PK, `student_id` (FK users), `schedule_id` (FK schedules), `enrolled_at`. UniqueConstraint on (student_id, schedule_id).
- **AttendanceRecord**: UUID PK, `student_id`/`schedule_id` (UUID FKs), `date`, `status` (enum), check_in/check_out times, presence metrics
- **PresenceLog**: Integer PK (BigInteger on PostgreSQL, Integer on SQLite via `.with_variant()`), `attendance_id` (UUID FK)
- **EarlyLeaveEvent**: UUID PK, `attendance_id` (UUID FK), detection timestamps, consecutive_misses count
- Relationships defined with `backref` (e.g., Schedule.faculty -> User.teaching_schedules, Enrollment.student -> User.enrollments)

## Patterns & Conventions
- `hash_password()` directly hashes without validation; `validate_password_strength()` is separate
- `db.flush()` to get IDs mid-transaction, `db.commit()` only at end for atomicity
- Idempotency checks use `.first()` query before insert
- Scripts use `sys.path.insert(0, ...)` to add backend dir for imports
- Run scripts from backend dir: `python -m scripts.seed_data`

## UUID Handling in Repositories (CRITICAL)
- **All repository `create()` methods MUST convert string UUIDs to `uuid.UUID` objects** before passing to models
- SQLAlchemy UUID columns with `UUID(as_uuid=True)` expect Python `uuid.UUID` objects, NOT strings
- Pattern for create methods:
```python
def create(self, data: dict) -> Model:
    data = data.copy()
    if "student_id" in data and isinstance(data["student_id"], str):
        data["student_id"] = uuid.UUID(data["student_id"])
    # ... convert all UUID fields
    return Model(**data)
```
- Foreign key UUIDs in presence_logs, early_leave_events, attendance_records all need conversion
- Query methods already convert: `Model.id == uuid.UUID(id_string)` pattern works correctly

## SQLite Test Compatibility
- **BigInteger autoincrement doesn't work in SQLite** - use `Integer().with_variant(BIGINT, "postgresql")`
- PresenceLog.id uses this pattern: works as Integer in tests, BigInteger in production
- Required imports: `from sqlalchemy.dialects.postgresql import BIGINT`

## Presence Service Business Rules
- **Start session**: Creates AttendanceRecord for all enrolled students with status=ABSENT
- **First detection (check-in)**: Determines PRESENT vs LATE based on grace period, logs presence, updates metrics
- **Scan cycle**: Runs every 60s, logs presence for all students (detected or not), increments scan counters
- **Early leave**: 3 consecutive misses triggers early_leave_event, status changed to EARLY_LEAVE
- **Service makes TWO update calls per detection**: (1) check_in_time + status, (2) scan metrics
- **Presence score**: `(scans_present / total_scans) * 100`

## Repository Method Patterns
- `get_by_id(id: str)` - converts to UUID in query
- `create(data: dict)` - MUST convert UUID fields in dict before model instantiation
- `get_early_leave_events(schedule_id)` - filters by schedule (for faculty view)
- `get_early_leave_events_by_attendance(attendance_id)` - filters by attendance record (for specific student)
- All UUID parameters are strings in method signatures, converted to UUID objects internally

## Test Patterns
- Mock tests with `call_args_list` when service makes multiple repo calls
- Integration tests use real DB, check final state after workflow
- Fixtures: `db_session`, `test_student`, `test_schedule`, `test_enrollment` for presence tests

## Seed Data (see `backend/scripts/seed_data.py`)
- Student: cjjutbaofficial@gmail.com / password123 / student_id=21-A-02177
- Faculty: faculty@gmail.com / 123 (bypasses validation intentionally)
- Room: Room 301, Engineering Building, capacity 40
- Schedules: CPE 301 Mon-Fri 07:00-22:00 (wide window for testing)
- Enrollments: student enrolled in all 5 schedules

## PresenceService Session State (CRITICAL)
- `active_sessions` is a **class-level dict** (`_active_sessions`) shared across all instances
- Each `__init__` sets `self.active_sessions = PresenceService._active_sessions` (same reference)
- This ensures sessions persist across API requests (each request creates a new service instance)
- Tests use `autouse` fixture `_clear_presence_sessions` in conftest to clear between tests
- All dict mutations (`[]`, `del`, `in`) work directly on the shared class dict

## Face Router Patterns
- `/recognize` endpoint decodes base64 directly to bytes (no PIL round-trip)
- `/process` (Edge API) still uses PIL decode for image validation (`validate_size=True`)
- Edge API wraps `schedule_repo.get_current_schedule()` in try/except for invalid UUID room_ids

## Recent Fixes (2026-02-12)
- Fixed PresenceService stateless session bug: `active_sessions` now class-level shared dict
- Fixed face router `/recognize` unnecessary PIL round-trip (base64 -> bytes directly)
- Fixed Edge API room_id UUID validation (catches ValueError from invalid UUID format)
- Added `_clear_presence_sessions` autouse fixture in conftest for test isolation

## Recent Fixes (2026-02-07)
- Fixed `AttendanceRepository.create()` to convert string UUIDs to UUID objects
- Fixed `AttendanceRepository.log_presence()` UUID conversion (attendance_id)
- Fixed `AttendanceRepository.create_early_leave_event()` UUID conversion
- Added `get_early_leave_events_by_attendance()` method for attendance-specific queries
- Fixed `PresenceLog.id` column to use Integer/BigInteger variant for SQLite compatibility
- Updated unit test to check both update calls in `log_detection()` flow
- Updated integration tests to use `get_early_leave_events_by_attendance()` correctly

## Test Results
- 496 tests passing, 1 skipped (as of 2026-02-12)
- 33/33 presence-related tests passing
- Run tests: `"venv\Scripts\python.exe" -m pytest -v` from backend dir
