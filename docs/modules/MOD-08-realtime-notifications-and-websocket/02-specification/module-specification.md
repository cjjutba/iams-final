# Module Specification

## Module
- ID: `MOD-08`
- Name: Realtime Notifications and WebSocket

## Auth Context
- **User-Facing (FUN-08-01, FUN-08-05):** WebSocket endpoint requires Supabase JWT (query param `token`). JWT `sub` must match path `user_id`.
- **System-Internal (FUN-08-02 to FUN-08-04):** Backend service functions invoked by MOD-06/MOD-07 — no JWT required.

## Purpose
Push attendance and early-leave updates to mobile clients in realtime via authenticated WebSocket connections.

## Function Categories

### User-Facing (WebSocket endpoint)
- `FUN-08-01`: Open authenticated WebSocket connections (Supabase JWT, all roles).
- `FUN-08-05`: Handle reconnect and stale connection cleanup.

### System-Internal (service layer)
- `FUN-08-02`: Publish attendance update events (called by MOD-06 attendance service).
- `FUN-08-03`: Publish early-leave events (called by MOD-07 presence service).
- `FUN-08-04`: Publish session-end summary events (called by session finalization flow).

## API Contract
- `WS /ws/{user_id}` — base path: `ws://localhost:8000/api/v1` (dev), `wss://` (prod)
- Auth: Supabase JWT passed as `token` query parameter during handshake
- Close code 4001: Unauthorized (missing/invalid/expired JWT)
- Close code 4003: Forbidden (`user_id` mismatch)

## Events
- `attendance_update` — attendance status change (from MOD-06)
- `early_leave` — early-leave detection (from MOD-07)
- `session_end` — class session summary (from session finalization)

## Data
- Ephemeral connection map (in-memory, keyed by `user_id`)
- Optional message delivery logs (disabled by default, `WS_ENABLE_DELIVERY_LOGS`)

## Screens
- `SCR-018` StudentNotificationsScreen
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-025` FacultyEarlyLeaveAlertsScreen
- `SCR-029` FacultyNotificationsScreen

## Cross-Module Coordination
| Module | Relationship |
|---|---|
| MOD-01 | JWT auth middleware (shared `get_current_user` dependency) |
| MOD-02 | User deletion → close active WebSocket connections for deleted user |
| MOD-06 | Attendance service invokes FUN-08-02 on status transitions |
| MOD-07 | Presence service invokes FUN-08-03 on early-leave detection |
| MOD-09 | Student mobile app consumes WebSocket events |
| MOD-10 | Faculty mobile app consumes WebSocket events |

## Done Criteria
- Event payloads match API docs (event envelope format, required fields, timezone offsets).
- Auth enforcement verified: invalid JWT → 4001, `user_id` mismatch → 4003.
- Reconnect behavior is stable on network interruptions (idempotent, no duplicate entries).
- Notification screens update without app restart.
- System-internal functions (FUN-08-02 to FUN-08-04) clearly separated from user-facing (FUN-08-01, FUN-08-05).
