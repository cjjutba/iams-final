# Integration Points

## Auth Integration
- Supabase JWT verification via shared `get_current_user` dependency (same as MOD-01/02/05/06).
- FUN-07-06 endpoints extract role from JWT claims (faculty/admin required).
- System-internal functions (FUN-07-01 to FUN-07-05) do not use JWT — invoked by presence service scan loop.

## Backend File Paths
- Router: `backend/app/routers/presence.py`
- Service: `backend/app/services/presence_service.py`, `backend/app/services/tracking_service.py`
- Repository: `backend/app/repositories/presence_repository.py`
- Models: `backend/app/models/presence_log.py`, `backend/app/models/early_leave_event.py`
- Auth dependency: `backend/app/utils/dependencies.py` (`get_current_user`)
- Schemas: `backend/app/schemas/presence.py`

## Backend Integrations
- Presence service runtime state engine (scan loop, counters, flagging).
- Attendance repository updates (status: present → early_leave via MOD-06).
- Schedule/enrollment lookup services (session context from MOD-05).

## API Integrations
- Presence read endpoints (GET /presence/{attendance_id}/logs, GET /presence/early-leaves).
- Attendance and WebSocket modules consuming presence outcomes.

## Cross-Module Integration
| Module | Direction | Integration | Data |
|---|---|---|---|
| MOD-01 | MOD-01 → MOD-07 | JWT verification | Supabase JWT for FUN-07-06 |
| MOD-02 | MOD-02 → MOD-07 | Cascade deletion | users → attendance → presence data |
| MOD-03 | MOD-03 → MOD-07 | Detection results | Recognized face IDs per scan |
| MOD-04 | MOD-04 → MOD-07 | Edge detection | Cropped face frames from RPi |
| MOD-05 | MOD-05 → MOD-07 | Session context | Schedule boundaries, enrolled students |
| MOD-06 | MOD-06 ↔ MOD-07 | Attendance context | FK reference, status update (present → early_leave) |
| MOD-08 | MOD-07 → MOD-08 | Alert broadcast | Early-leave event payload for WebSocket |

## Timezone Integration
- Session boundaries use `TIMEZONE` env var (default: Asia/Manila, +08:00).
- "Today" queries for session context use configured timezone, not UTC.
- All TIMESTAMPTZ columns (scan_time, detected_at, last_seen_at, notified_at) include timezone offset.

## User Lifecycle Integration
- User deletion (MOD-02) cascades: `users` → `attendance_records` (MOD-06) → `presence_logs` + `early_leave_events` (MOD-07).
- All presence data for a deleted user is removed via FK cascade.
