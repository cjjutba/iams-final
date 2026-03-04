# Step 6: Seed the Database

Seeding populates the database with initial data that the system needs to function: faculty accounts, rooms, class schedules, and student records.

---

## Prerequisites

- Migrations completed (Step 5)
- Virtual environment is activated (`(venv)` in your prompt)
- You are in the `backend/` folder

---

## Option A: Seed for Pilot Testing (Recommended)

Use this for real pilot testing where students will register themselves:

```bash
python -m scripts.seed_all --no-sim
```

This creates:
- **1 faculty account** — for logging in and managing attendance
- **3 rooms** — classroom locations
- **13 class schedules** — pre-configured class schedules
- **2 student records** — in the school registry (for testing registration)

---

## Option B: Seed with Simulation Data

Use this if you want pre-made student accounts and attendance history for demonstration:

```bash
python -m scripts.seed_all
```

This creates everything from Option A, plus:
- Simulated student user accounts
- Enrollment records
- Attendance history

---

## Expected Output

```
============================================================
IAMS - Full Development Seed
============================================================

>>> Step 1: Reference Data (student_records + faculty_records)
  [student_records] Seeded 1 record(s)
  [faculty_records] Seeded 1 record(s)

>>> Step 2: Operational Data (faculty user, rooms, schedules)
  [Faculty User] Created: faculty@gmail.com
  [Rooms] Created 3 room(s)
  [Schedules] Created 13 schedule(s)

>>> Step 3: Content Data (faculty notifications)
  [Notifications] Created notifications for faculty

>>> Step 4: Simulation Data — SKIPPED (--no-sim)

============================================================
ALL SEED DATA COMPLETE
============================================================

Ready for development/testing.

Faculty login: faculty@gmail.com / password123

Student registration: use mobile app with a Student ID from seed_reference_data
```

---

## Seed Data Summary

### Faculty Account
| Field | Value |
|-------|-------|
| Email | faculty@gmail.com |
| Password | password123 |
| Role | Faculty |

### Test Student Records
| Field | Student 1 | Student 2 |
|-------|-----------|-----------|
| Student ID | 21-A-02177 | 21-A-01234 |
| Name | Christian Jerald Jutba | Juhazelle Espela |
| Course | BSCPE | BSCPE |
| Year Level | 4 | 4 |
| Section | A | A |
| Birthday | 2003-01-13 | 2003-01-03 |

> **Note:** Student records are in the school registry (`student_records` table). Students still need to register through the mobile app to create their user accounts and face data.

---

## Running Seeds Again

All seed scripts are **idempotent** — they skip records that already exist. It is safe to run the seed command multiple times.

---

**Next step:** [07 - Start the Backend Server](../07-start-backend/README.md)
