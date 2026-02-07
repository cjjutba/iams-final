# Endpoint Contract: Early-Leave and Class Summary

## Scope
Endpoints for early-leave alerts, presence detail, and class summary/history context.

## Endpoints
- `GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD`
- `GET /presence/{attendance_id}/logs`
- `GET /attendance/today?schedule_id=uuid`
- `GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

## Client Rules
1. Apply selected class/date filters before request.
2. Display clear empty state when no early-leave events exist.
3. Keep summary cards aligned with returned attendance totals.

## Screens
- `SCR-022` FacultyClassDetailScreen
- `SCR-023` FacultyStudentDetailScreen
- `SCR-025` FacultyEarlyLeaveAlertsScreen
- `SCR-026` FacultyReportsScreen
