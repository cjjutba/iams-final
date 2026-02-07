# MVP Scope

## In Scope
- Authenticated WebSocket endpoint: `WS /ws/{user_id}`.
- Event publishing:
  - `attendance_update`
  - `early_leave`
  - `session_end`
- Basic heartbeat support (ping/pong) and liveness handling.
- Reconnect-safe client behavior and server stale cleanup.
- Notification-screen realtime update integration for:
  - `SCR-018` StudentNotificationsScreen
  - `SCR-029` FacultyNotificationsScreen
  - `SCR-021` FacultyLiveAttendanceScreen

## Out of Scope
- Background push delivery when app is terminated.
- Guaranteed once-only delivery with persistent queue.
- Multi-region realtime fanout and broker clusters.
- Full notification preference management UI.

## Dependency Scope Notes
- Attendance and presence state is produced by `MOD-06` and `MOD-07`.
- MOD-08 only transports already-computed events to connected clients.
