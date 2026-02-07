# Capabilities Matrix

| Capability | Function IDs | API/Event | Primary Data | Screens |
|---|---|---|---|---|
| Authenticated websocket session | FUN-08-01 | `WS /ws/{user_id}` | connection map | SCR-018, SCR-029, SCR-021 |
| Attendance update fanout | FUN-08-02 | `attendance_update` | payload schema, delivery log (optional) | SCR-021, SCR-029 |
| Early-leave alert fanout | FUN-08-03 | `early_leave` | payload schema, delivery log (optional) | SCR-025, SCR-029, SCR-021 |
| Session-end summary fanout | FUN-08-04 | `session_end` | payload schema, delivery log (optional) | SCR-018, SCR-029, SCR-021 |
| Reconnect and stale cleanup | FUN-08-05 | connection lifecycle | connection map | SCR-018, SCR-029, SCR-021 |

## Readiness Gates
- Gate A: Endpoint auth and identity matching complete.
- Gate B: Three core events published with validated payload shape.
- Gate C: Reconnect path tested under network interruption.
