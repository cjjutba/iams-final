# Step 5: Run Database Migrations

Migrations create all the database tables that the system needs. This only needs to be done once (or when the schema changes).

---

## Prerequisites

- Database is running (`docker compose up -d` from Step 3)
- Virtual environment is activated (`(venv)` in your prompt)
- You are in the `backend/` folder

---

## Run the migrations

```bash
alembic upgrade head
```

You should see output like:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> e49171084f7c, Initial schema - create 8 tables
INFO  [alembic.runtime.migration] Running upgrade e49171084f7c -> 53db1ce6f3d0, Add Supabase auth columns
INFO  [alembic.runtime.migration] Running upgrade 53db1ce6f3d0 -> 64622432db30, Add student_records and faculty_records
INFO  [alembic.runtime.migration] Running upgrade 64622432db30 -> 86d63351d3e9, Add notifications table
INFO  [alembic.runtime.migration] Running upgrade 86d63351d3e9 -> 7bf7e45a61d8, Add birthdate/contact to student_records
INFO  [alembic.runtime.migration] Running upgrade 7bf7e45a61d8 -> a1b2c3d4e5f6, Add target_course/year to schedules
```

---

## What was created

The migrations create 12 tables in the database:

| Table | Purpose |
|-------|---------|
| `users` | All user accounts (students, faculty, admin) |
| `student_records` | School's official student registry |
| `faculty_records` | School's official faculty registry |
| `face_registrations` | Links users to their face embeddings |
| `rooms` | Classroom locations |
| `schedules` | Class schedules (subject, faculty, room, time) |
| `enrollments` | Which students are enrolled in which classes |
| `attendance_records` | Check-in records for each session |
| `presence_logs` | Periodic scan results (every 60 seconds) |
| `early_leave_events` | Early leave detections |
| `notifications` | System notifications for users |
| `alembic_version` | Tracks which migrations have been applied |

---

## Verify

You can verify the tables were created by running:

```bash
docker exec -it iams-postgres psql -U postgres -d iams -c "\dt public.*"
```

This should list all 12 tables.

---

**Next step:** [06 - Seed the Database](../06-seed-database/README.md)
