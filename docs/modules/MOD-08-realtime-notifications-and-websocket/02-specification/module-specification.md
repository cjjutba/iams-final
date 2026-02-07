# Module Specification

## Module
- ID: `MOD-08`
- Name: Realtime Notifications and WebSocket

## Purpose
Push attendance and early-leave updates to mobile clients in realtime.

## Functions
- `FUN-08-01`: Open authenticated WebSocket connections.
- `FUN-08-02`: Publish attendance update events.
- `FUN-08-03`: Publish early-leave events.
- `FUN-08-04`: Publish session-end summary events.
- `FUN-08-05`: Handle reconnect and stale connection cleanup.

## API Contract
- `WS /ws/{user_id}`

## Events
- `attendance_update`
- `early_leave`
- `session_end`

## Data
- Ephemeral connection map
- Optional message delivery logs

## Screens
- `SCR-018` StudentNotificationsScreen
- `SCR-029` FacultyNotificationsScreen
- `SCR-021` FacultyLiveAttendanceScreen

## Done Criteria
- Event payloads match API docs.
- Reconnect behavior is stable on network interruptions.
- Notification screens update without app restart.
