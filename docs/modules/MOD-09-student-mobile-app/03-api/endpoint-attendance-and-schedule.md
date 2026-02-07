# Endpoint Contract: Attendance and Schedule

## Scope
Endpoints that power student home, schedule, and history views.

## Endpoints
- `GET /schedules/me`
- `GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /attendance/today?schedule_id=uuid` (contextual per-class today view)

## Client Behavior
1. Fetch schedule and attendance in parallel when appropriate.
2. Render loading/empty/error states per screen.
3. Preserve date-filter query consistency between UI and API.

## Screens
- `SCR-011` StudentHomeScreen
- `SCR-012` StudentScheduleScreen
- `SCR-013` StudentAttendanceHistoryScreen
- `SCR-014` StudentAttendanceDetailScreen
