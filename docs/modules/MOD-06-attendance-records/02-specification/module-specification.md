# Module Specification

## Module ID
`MOD-06`

## Purpose
Record attendance events and expose history/live class data.

## Core Functions
- `FUN-06-01`: Mark attendance from recognition events.
- `FUN-06-02`: Return today's attendance for a class.
- `FUN-06-03`: Return student personal attendance history.
- `FUN-06-04`: Return filtered attendance records.
- `FUN-06-05`: Allow manual attendance entry by faculty.
- `FUN-06-06`: Return live attendance roster for active class.

## API Contracts
- `GET /attendance/today?schedule_id=uuid`
- `GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `POST /attendance/manual`
- `GET /attendance/live/{schedule_id}`

## Data Dependencies
- `attendance_records`
- `schedules`
- `users`

## Screen Dependencies
- `SCR-011` StudentHomeScreen
- `SCR-013` StudentAttendanceHistoryScreen
- `SCR-014` StudentAttendanceDetailScreen
- `SCR-019` FacultyHomeScreen
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-024` FacultyManualEntryScreen

## Done Criteria
- Duplicate attendance marking for same student/session is prevented.
- Manual override is auditable.
- History queries support date filters.
