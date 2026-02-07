# Endpoint Contract: Schedule and Active Class

## Scope
Endpoints and rules used to show faculty schedule and resolve active class.

## Endpoints
- `GET /schedules/me`
- `GET /schedules/{id}/students`

## Active Class Resolution
1. Load all faculty schedules for current day context.
2. Determine active class by comparing current time against schedule bounds.
3. If active, route to live attendance screen context.

## Screens
- `SCR-019` FacultyHomeScreen
- `SCR-020` FacultyScheduleScreen
- `SCR-021` FacultyLiveAttendanceScreen
