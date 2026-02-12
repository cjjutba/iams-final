# Attendance Records Module Catalog

## Auth Context
All MOD-06 endpoints require Supabase JWT (`Authorization: Bearer <token>`). Role determines access scope — see per-subdomain auth notes below.

## Subdomains
1. Attendance Marking
- Create/update attendance rows from recognition events.
- **Auth:** System-triggered (internal pipeline from MOD-03/MOD-07). Not a user-facing endpoint.

2. Daily Class Attendance View
- Return today's roster, statuses, and summary counts for a schedule.
- **Auth:** Faculty or admin only (Supabase JWT + role check).

3. Student History View
- Return attendance timeline for student with date range filters (`start_date`, `end_date`).
- **Auth:** Student sees own records; faculty/admin can query any student.

4. Class History Query
- Return filtered attendance records for schedule/date windows.
- **Auth:** Faculty or admin only.

5. Manual Attendance Operations
- Faculty override/create attendance rows with audit remarks.
- **Auth:** Faculty or admin only. 403 for student role.

6. Live Attendance Session View
- Return active session roster and current detection state.
- **Auth:** Faculty or admin only.

## Function Catalog
| Function ID | Name | Summary | Auth |
|---|---|---|---|
| FUN-06-01 | Mark Attendance | mark/check-in/update attendance row from recognition | system/internal |
| FUN-06-02 | Get Today's Attendance | class summary and records for current date | faculty/admin |
| FUN-06-03 | Get My Attendance | student personal attendance history | any authenticated (role-scoped) |
| FUN-06-04 | Get Attendance History | filtered class attendance list | faculty/admin |
| FUN-06-05 | Manual Attendance Entry | faculty manual entry/override with remarks | faculty/admin |
| FUN-06-06 | Get Live Attendance | active class roster with live statuses | faculty/admin |

## Actors
- Student: view own attendance (Supabase JWT, student role)
- Faculty: view class attendance, manual entry, live monitoring (Supabase JWT, faculty role)
- Admin: full access to all attendance data (Supabase JWT, admin role)
- Backend recognition pipeline: system-level attendance marking (MOD-03/MOD-07)
- Attendance service: business logic layer

## Interfaces
- REST attendance endpoints (`/api/v1/attendance/*`) — Supabase JWT required
- SQLAlchemy `AttendanceRecord` model → `attendance_records` table
- Foreign keys: `student_id` → `users.id`, `schedule_id` → `schedules.id`
- Response envelope: `{ "success": true, "data": {}, "message": "" }`
