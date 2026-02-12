# Goal and Objectives

## Module Goal
Record attendance events accurately from recognition inputs and expose student/faculty attendance views, history, and live class states — secured with Supabase JWT and role-based access control.

## Auth Context
All MOD-06 endpoints require Supabase JWT (`Authorization: Bearer <token>`). Role determines access: faculty/admin can view class attendance and perform manual overrides; students can view their own attendance history. Attendance marking from the recognition pipeline is an internal system operation triggered by MOD-03/MOD-07.

## Primary Objectives
1. Mark attendance for recognized students with dedup safeguards (unique per `student_id + schedule_id + date`).
2. Provide today's class attendance summary and records (faculty/admin, filtered by `schedule_id`).
3. Provide student personal attendance history with date range filters (`start_date`, `end_date`).
4. Provide generic filtered attendance history queries (faculty/admin, by schedule/date range).
5. Support faculty manual attendance overrides with audit remarks (`remarks`, `updated_by`, `updated_at`).
6. Provide live attendance roster for active class monitoring (faculty/admin, real-time session state).
7. Provide attendance context for downstream modules (MOD-07 presence tracking, MOD-08 notifications/alerts).

## Success Outcomes
- Duplicate attendance rows for same student/schedule/date are prevented.
- History endpoints return correct data ranges using configured timezone (TIMEZONE env var, default: Asia/Manila).
- Manual entries are auditable and role-restricted (faculty/admin only).
- Live attendance view is consistent with backend session state.
- Missing/invalid JWT returns 401; insufficient role returns 403.

## Non-Goals (for MOD-06 MVP)
- Full analytics dashboards.
- Advanced reporting exports (handled by later modules).
- Presence scan algorithm (owned by MOD-07).
- Rate limiting (thesis demonstration, not production).
- Direct attendance creation API for students (attendance is system-generated from recognition).

## Stakeholders
- Students: view own attendance status and history.
- Faculty: monitor live attendance, view class attendance, perform manual entry/override.
- Admin: full access to all attendance data.
- MOD-03 (Face Recognition): triggers attendance marking on successful recognition.
- MOD-05 (Schedules): provides schedule_id context for attendance records.
- MOD-07 (Presence Tracking): uses attendance records as input for presence scoring.
- Backend consumers: use attendance records for notifications/reports.
