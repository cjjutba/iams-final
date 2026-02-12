# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-08`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-08` and at least one `FUN-08-*` ID.

## Scope Control
- Implement only `FUN-08-01` to `FUN-08-05` under this module.
- Do not add new WebSocket event types unless docs are updated first.
- FUN-08-01 and FUN-08-05 are user-facing (WebSocket endpoint with JWT auth).
- FUN-08-02 to FUN-08-04 are system-internal service functions (invoked by MOD-06/MOD-07, no JWT).
- Module 8 publishes events; it does not compute attendance/presence logic (owned by MOD-06/MOD-07).

## Auth Rules
1. WebSocket connections require valid Supabase JWT (passed as `token` query parameter during handshake).
2. JWT `sub` claim must match path `user_id`.
3. Reject missing/invalid/expired JWT with WebSocket close code 4001 (Unauthorized).
4. Reject `user_id` mismatch with close code 4003 (Forbidden).
5. All authenticated roles (student, faculty, admin) can connect to their own WebSocket.
6. No API key auth — that pattern is for MOD-03/MOD-04 edge devices only.
7. System-internal functions (FUN-08-02 to FUN-08-04) do not require JWT (invoked by backend service layer).

## Timezone Rules
1. `TIMEZONE` env var configures the system timezone (default: Asia/Manila, +08:00).
2. All event timestamps use ISO-8601 format with timezone offset (e.g., `2026-02-12T08:05:00+08:00`).
3. Session-end events reference schedule dates in the configured timezone.

## Connection Rules
1. Event payloads must stay consistent with `03-api/` contracts.
2. Reconnect behavior must be idempotent: evict stale entry for same `user_id` before registering new socket.
3. Only one active socket per `user_id` at a time (reconnect replaces old).
4. Stale connection cleanup is required on disconnect/error/heartbeat timeout.
5. Connection map stays bounded — enforce `WS_MAX_CONNECTIONS_PER_USER` cap (default: 3).
6. Heartbeat/liveness checks every `WS_HEARTBEAT_INTERVAL` seconds (default: 30).

## Quality Rules
- Event envelope shape is fixed: `{ "type": "...", "data": { ... } }`.
- Only documented events (`attendance_update`, `early_leave`, `session_end`) are emitted in MVP.
- Send failures are logged with user and event metadata — silent drop is not allowed.
- Event payloads are additive-only for MVP: new optional fields OK, never remove required fields.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-08 FUN-08-01`
- Any event contract change must update:
  - `03-api/` event docs
  - `04-data/event-payload-schema.md`
  - `10-traceability/traceability-matrix.md`

## Change Process
1. Propose doc updates.
2. Review consistency across API/data/screens/testing docs.
3. Implement code.
4. Run tests.
5. Update traceability and changelog.
