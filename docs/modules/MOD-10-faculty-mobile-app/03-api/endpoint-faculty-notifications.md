# Endpoint Contract: Faculty Notifications

## Scope
Realtime event stream used by faculty notification and live-class screens.

## Endpoint
- `WS /ws/{user_id}`

## Event Types
- `attendance_update`
- `early_leave`
- `session_end`

## Client Rules
1. Connect only after faculty auth/session readiness.
2. Render reconnecting state during network loss.
3. Resume stream without app restart.
4. Parse event envelope safely and ignore unknown types.

## Screens
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-029` FacultyNotificationsScreen
