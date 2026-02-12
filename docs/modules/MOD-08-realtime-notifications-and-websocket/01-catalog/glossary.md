# Glossary

- **WebSocket:** Bidirectional persistent protocol between client and server over a single TCP connection.
- **Connection map:** In-memory registry of active sockets keyed by `user_id`.
- **Fanout:** Sending one logical event to one or more connected recipients.
- **Stale connection:** Socket entry that is no longer valid (heartbeat timeout, send failure) but still tracked in the map.
- **Heartbeat:** Ping/pong exchange at `WS_HEARTBEAT_INTERVAL` (default 30s) used to detect dead connections.
- **Reconnect:** Client-initiated new socket after disconnect; must be idempotent (evict stale, register new).
- **Event envelope:** Standard top-level JSON shape: `{ "type": "...", "data": { ... } }`.
- **Session end:** End-of-class summary event emitted after class session closes, containing attendance count totals.
- **Supabase JWT:** JSON Web Token issued by Supabase Auth, containing `sub` (user ID) and `role` claims. Used for WebSocket handshake auth.
- **Close code 4001:** Custom WebSocket close code for Unauthorized (missing/invalid/expired JWT).
- **Close code 4003:** Custom WebSocket close code for Forbidden (`user_id` path mismatch with JWT `sub`).
- **System-internal function:** Backend service function invoked by other modules (MOD-06/MOD-07), not exposed as an HTTP/WS endpoint.
- **Notification service:** Backend service (`notification_service.py`) that manages the connection map and event publishing.
- **Timezone:** System timezone configured via `TIMEZONE` env var (default: Asia/Manila, +08:00). All event timestamps include timezone offset.
