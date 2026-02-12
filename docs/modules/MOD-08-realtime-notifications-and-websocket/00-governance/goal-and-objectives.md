# Goal and Objectives

## Module Goal
Deliver stable realtime attendance and early-leave notifications from backend to mobile clients using authenticated WebSocket connections.

## Auth Context
- WebSocket connections require Supabase JWT (passed as `token` query parameter during handshake).
- JWT `sub` must match path `user_id`; all authenticated roles (student, faculty, admin) can connect.
- Event publishing functions (FUN-08-02 to FUN-08-04) are system-internal — invoked by MOD-06/MOD-07 service layer, no JWT required.

## Problem Statement
Attendance and early-leave state changes are time-sensitive. Polling APIs alone can cause delay, stale screens, and weak classroom monitoring.

## Objectives
1. Open and maintain authenticated WebSocket sessions per user (`WS /ws/{user_id}`, Supabase JWT auth).
2. Publish standardized events (`attendance_update`, `early_leave`, `session_end`) with consistent envelope format.
3. Keep mobile notification screens (SCR-018, SCR-021, SCR-025, SCR-029) in sync without app restart.
4. Handle disconnect/reconnect and stale connection cleanup safely (idempotent reconnect, no duplicate map entries).
5. Preserve clean boundaries — MOD-08 transports events; MOD-06/MOD-07 compute state.
6. Use `TIMEZONE` (Asia/Manila, +08:00) for all event timestamps.

## Stakeholders
- **Faculty (MOD-10):** Receive real-time attendance updates and early-leave alerts during live class.
- **Students (MOD-09):** Receive session-end summaries and routed notifications.
- **Presence service (MOD-07):** Triggers early-leave event publishing via FUN-08-03.
- **Attendance service (MOD-06):** Triggers attendance update publishing via FUN-08-02.

## MVP Success Signals
- Faculty sees attendance updates in near real time during live class.
- Faculty receives early-leave alert events during session.
- Student and faculty notification screens reflect new events after reconnect.
- No unbounded growth in connection map or stale sessions.
- Invalid/expired JWT connections are rejected with appropriate close codes (4001/4003).

## Non-Goals for MOD-08
- Push notifications through FCM/APNs.
- Guaranteed durable message queue for offline clients.
- Analytics dashboards for notification metrics.
- Role-based event filtering (all events routed to connected user in MVP).
