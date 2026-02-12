# MVP Scope

## In Scope
- Authenticated WebSocket endpoint: `WS /ws/{user_id}` with Supabase JWT auth (query param `token`).
- JWT validation: reject invalid/expired tokens (close code 4001), reject `user_id` mismatch (close code 4003).
- Event publishing (system-internal, no JWT):
  - `attendance_update` — triggered by MOD-06 attendance service
  - `early_leave` — triggered by MOD-07 presence service
  - `session_end` — triggered by session finalization flow
- Event envelope format: `{ "type": "...", "data": { ... } }`.
- All event timestamps use `TIMEZONE` (default: Asia/Manila, +08:00) with ISO-8601 format.
- Basic heartbeat support (ping/pong at `WS_HEARTBEAT_INTERVAL`, default 30s) and liveness handling.
- Stale connection cleanup at `WS_STALE_TIMEOUT` (default 60s).
- Reconnect-safe client behavior: idempotent reconnect, evict stale entry for same `user_id` before registering new socket.
- Notification-screen realtime update integration for:
  - `SCR-018` StudentNotificationsScreen
  - `SCR-021` FacultyLiveAttendanceScreen
  - `SCR-025` FacultyEarlyLeaveAlertsScreen
  - `SCR-029` FacultyNotificationsScreen

## Out of Scope
- Background push delivery when app is terminated (FCM/APNs).
- Guaranteed once-only delivery with persistent queue.
- Multi-region realtime fanout and broker clusters.
- Full notification preference management UI.
- Role-based event filtering (all events routed to connected user in MVP).

## Dependency Scope Notes
- Attendance and presence state is produced by `MOD-06` and `MOD-07`.
- MOD-08 only transports already-computed events to connected clients.
- Auth middleware shared with MOD-01 (Supabase JWT verification via `get_current_user`).

## Gate Criteria
- [ ] WebSocket endpoint accepts valid JWT and rejects invalid/expired tokens.
- [ ] `user_id` mismatch correctly rejected with close code 4003.
- [ ] All 3 event types delivered with valid envelope and payload fields.
- [ ] Reconnect after network drop resumes event stream without app restart.
- [ ] No stale connection growth after repeated reconnect cycles.
- [ ] Event timestamps include timezone offset (`+08:00`).
