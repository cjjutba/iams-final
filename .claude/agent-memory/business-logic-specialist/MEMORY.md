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
- Relationships defined with `backref` (e.g., Schedule.faculty -> User.teaching_schedules, Enrollment.student -> User.enrollments)

## Patterns & Conventions
- `hash_password()` directly hashes without validation; `validate_password_strength()` is separate
- `db.flush()` to get IDs mid-transaction, `db.commit()` only at end for atomicity
- Idempotency checks use `.first()` query before insert
- Scripts use `sys.path.insert(0, ...)` to add backend dir for imports
- Run scripts from backend dir: `python -m scripts.seed_data`

## Seed Data (see `backend/scripts/seed_data.py`)
- Student: cjjutbaofficial@gmail.com / password123 / student_id=21-A-02177
- Faculty: faculty@gmail.com / 123 (bypasses validation intentionally)
- Room: Room 301, Engineering Building, capacity 40
- Schedules: CPE 301 Mon-Fri 07:00-22:00 (wide window for testing)
- Enrollments: student enrolled in all 5 schedules
