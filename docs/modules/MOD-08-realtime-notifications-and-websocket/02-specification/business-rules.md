# Business Rules

## Auth Rules
1. WebSocket access requires valid Supabase JWT (query parameter `token`).
2. JWT `sub` claim must match path `user_id` — reject with close code 4003 on mismatch.
3. Missing/invalid/expired JWT — reject with close code 4001.
4. All authenticated roles (student, faculty, admin) can connect to their own WebSocket.
5. System-internal functions (FUN-08-02 to FUN-08-04) do not require JWT — invoked by backend service layer.

## Timezone Rules
1. `TIMEZONE` env var configures the system timezone (default: Asia/Manila, +08:00).
2. All event timestamps use ISO-8601 format with timezone offset (e.g., `2026-02-12T08:05:00+08:00`).
3. Session-end events reference schedule dates in the configured timezone.
4. Mobile clients should display timestamps using the offset provided in the event payload.

## Event Rules
1. Event envelope shape is fixed: `{ "type": "...", "data": { ... } }`.
2. Only documented events (`attendance_update`, `early_leave`, `session_end`) are emitted in MVP.
3. Event payload fields are additive-only: new optional fields OK, never remove required fields.
4. Notification service does not generate attendance/presence truth — it relays validated upstream events from MOD-06/MOD-07.
5. Session-end event should be emitted once per schedule/date session.

## Connection Rules
1. Reconnect behavior must be idempotent: evict stale entry for same `user_id` before registering new.
2. Only one active socket per `user_id` at a time (reconnect replaces old).
3. Connection map stays bounded — enforce `WS_MAX_CONNECTIONS_PER_USER` cap (default: 3).
4. Heartbeat/liveness checks at `WS_HEARTBEAT_INTERVAL` (default: 30s) detect dead sockets.
5. Stale connections removed after `WS_STALE_TIMEOUT` (default: 60s) without pong response.

## Delivery Rules
1. Send failures are logged with user and event metadata — silent drop is not allowed.
2. Failed sends mark connection for cleanup (do not retry to dead socket indefinitely).
3. Optional delivery logging controlled by `WS_ENABLE_DELIVERY_LOGS` (default: disabled).

## Data Integrity Rules
1. MOD-08 does not create or modify any relational database tables in MVP (ephemeral data only).
2. User deletion (MOD-02) should trigger: close active WebSocket connection for deleted user, remove from connection map.
3. Event payloads must reference valid entity IDs (student_id, schedule_id) from upstream modules.
