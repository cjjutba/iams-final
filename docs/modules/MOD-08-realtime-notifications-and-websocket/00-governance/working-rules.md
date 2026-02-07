# Working Rules

1. Implement only `FUN-08-01` to `FUN-08-05` for Module 8 tasks.
2. Do not add new WebSocket event types unless docs are updated first.
3. Event payloads must stay consistent with `03-api/` contracts.
4. Connection auth is mandatory; unauthenticated sockets are rejected.
5. `user_id` in WebSocket path must match authenticated identity.
6. Reconnect behavior must be idempotent and avoid duplicate connection entries.
7. Stale connection cleanup is required on disconnect/error.
8. Module 8 publishes events; it does not compute attendance/presence logic.
9. If contracts conflict with upstream docs, stop and update docs first.
10. Every implementation commit should mention `MOD-08` and at least one `FUN-08-*`.
