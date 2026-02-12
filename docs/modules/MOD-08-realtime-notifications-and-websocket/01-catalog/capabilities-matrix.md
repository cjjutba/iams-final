# Capabilities Matrix

| Capability | Function IDs | Auth Requirement | API/Event | Primary Data | Screens |
|---|---|---|---|---|---|
| Authenticated websocket session | FUN-08-01 | Supabase JWT (query param `token`) | `WS /ws/{user_id}` | connection map | SCR-018, SCR-021, SCR-025, SCR-029 |
| Attendance update fanout | FUN-08-02 | System-internal (no JWT) | `attendance_update` event | payload schema | SCR-021, SCR-029 |
| Early-leave alert fanout | FUN-08-03 | System-internal (no JWT) | `early_leave` event | payload schema | SCR-021, SCR-025, SCR-029 |
| Session-end summary fanout | FUN-08-04 | System-internal (no JWT) | `session_end` event | payload schema | SCR-018, SCR-021, SCR-029 |
| Reconnect and stale cleanup | FUN-08-05 | Supabase JWT (reconnect) | connection lifecycle | connection map | SCR-018, SCR-021, SCR-025, SCR-029 |

## Per-Role Access
| Role | WS Connect | Receive attendance_update | Receive early_leave | Receive session_end |
|---|---|---|---|---|
| Student | Own user_id only | Yes (own records) | No (faculty-targeted) | Yes |
| Faculty | Own user_id only | Yes (class records) | Yes | Yes |
| Admin | Own user_id only | Yes | Yes | Yes |

## Auth Note
- All roles connect to `WS /ws/{user_id}` with their own JWT — no cross-user access.
- Event routing to specific roles is handled by the notification service (FUN-08-02/03/04), not by the WebSocket endpoint itself.

## Readiness Gates
- Gate A: Endpoint auth and identity matching complete (4001/4003 close codes).
- Gate B: Three core events published with validated payload shape and timezone offsets.
- Gate C: Reconnect path tested under network interruption with idempotent behavior.
