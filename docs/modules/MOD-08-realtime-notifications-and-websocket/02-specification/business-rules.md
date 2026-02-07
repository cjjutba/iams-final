# Business Rules

1. WebSocket access requires authenticated identity.
2. Path `user_id` must match authenticated user identity.
3. Event envelope shape is fixed: `{ "type": "...", "data": { ... } }`.
4. Only documented events (`attendance_update`, `early_leave`, `session_end`) are emitted in MVP.
5. Notification service does not generate attendance/presence truth; it relays validated upstream events.
6. Event payload fields are additive only under documented versioning decision.
7. Send failures are logged with user and event metadata.
8. Heartbeat/liveness checks are used to remove dead sockets.
9. Reconnect should restore stream without app restart.
10. Connection map stays bounded and cleaned on disconnect.
