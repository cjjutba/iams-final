# Module Specification

## Module ID
`MOD-06`

## Purpose
Record attendance events and expose history/live class data — secured with Supabase JWT and role-based access control.

## Auth Context
All MOD-06 endpoints require Supabase JWT (`Authorization: Bearer <token>`). No API key auth (that pattern is for MOD-03/MOD-04 edge devices only).

## Base Path
`/api/v1/attendance`

## Core Functions
- `FUN-06-01`: Mark attendance from recognition events (system/internal).
- `FUN-06-02`: Return today's attendance for a class (faculty/admin).
- `FUN-06-03`: Return student personal attendance history (any authenticated, role-scoped).
- `FUN-06-04`: Return filtered attendance records (faculty/admin).
- `FUN-06-05`: Allow manual attendance entry by faculty (faculty/admin).
- `FUN-06-06`: Return live attendance roster for active class (faculty/admin).

## API Contracts
- `GET /attendance/today?schedule_id=uuid` — Supabase JWT, faculty/admin
- `GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — Supabase JWT, any authenticated (role-scoped)
- `GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — Supabase JWT, faculty/admin
- `POST /attendance/manual` — Supabase JWT, faculty/admin
- `GET /attendance/live/{schedule_id}` — Supabase JWT, faculty/admin

## Data Dependencies
- `attendance_records` — core table (FK: student_id → users.id, schedule_id → schedules.id)
- `schedules` — schedule context (from MOD-05)
- `users` — student/faculty identity (from MOD-02)
- `enrollments` — enrollment validation (from MOD-05)

## Screen Dependencies
- `SCR-011` StudentHomeScreen
- `SCR-013` StudentAttendanceHistoryScreen
- `SCR-014` StudentAttendanceDetailScreen
- `SCR-019` FacultyHomeScreen
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-024` FacultyManualEntryScreen

## Cross-Module Coordination
- **MOD-03 (Face Recognition):** Recognition result triggers FUN-06-01 attendance marking.
- **MOD-04 (Edge Device):** Edge device captures feed into recognition pipeline that ultimately marks attendance.
- **MOD-05 (Schedules):** Provides schedule_id context. Active schedule detection determines which class attendance is marked for.
- **MOD-07 (Presence Tracking):** Uses attendance records for presence scoring and early-leave detection.
- **MOD-02 (User Management):** User deletion should cascade to attendance records (data integrity).

## Done Criteria
- Duplicate attendance marking for same student/schedule/date is prevented.
- Manual override is auditable (remarks, updated_by, updated_at).
- History queries support date range filters.
- Auth enforcement verified: 401 for missing/invalid JWT, 403 for insufficient role.
- Timezone configuration validated (date comparisons use TIMEZONE env var).
- Response envelope consistent: `{ "success": true, "data": {}, "message": "" }`.
