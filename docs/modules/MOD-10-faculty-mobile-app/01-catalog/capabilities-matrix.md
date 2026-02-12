# Capabilities Matrix

| Capability | Function IDs | Auth Requirement | API/Events | Primary Screens |
|---|---|---|---|---|
| Faculty auth and restore | FUN-10-01 | Pre-auth (login) → Post-auth (session) | `/auth/login`, `/auth/refresh`, `/auth/me` | SCR-005, SCR-006, SCR-019 |
| Faculty schedule + active class | FUN-10-02 | Post-auth (JWT required) | `/schedules/me`, `/attendance/live/{schedule_id}` | SCR-019, SCR-020, SCR-021 |
| Live attendance view | FUN-10-03 | Post-auth (JWT) + WebSocket (JWT via query param) | `/attendance/live/{schedule_id}`, `attendance_update` | SCR-021, SCR-022, SCR-023 |
| Manual attendance control | FUN-10-04 | Post-auth (JWT required) | `/attendance/manual`, `/attendance/today` | SCR-024, SCR-021 |
| Early-leave + summary visibility | FUN-10-05 | Post-auth (JWT) + WebSocket events | `/presence/early-leaves`, `/attendance/today`, `session_end`, `early_leave` | SCR-025, SCR-022, SCR-026 |
| Faculty profile + notification feed | FUN-10-06 | Post-auth (JWT) + WebSocket (JWT via query param) | `/users/{id}`, `/auth/me`, `WS /ws/{user_id}?token=<jwt>` | SCR-027, SCR-028, SCR-029 |

## Per-Screen Auth Map
| Screen Group | Screens | Auth Status |
|---|---|---|
| Auth screens | SCR-005, SCR-006 | Pre-auth |
| Home / Schedule | SCR-019, SCR-020 | Post-auth |
| Live / Class operations | SCR-021, SCR-022, SCR-023, SCR-024, SCR-025, SCR-026 | Post-auth |
| Profile / Notifications | SCR-027, SCR-028, SCR-029 | Post-auth |

## Readiness Gates
- Gate A: Faculty login, token persistence in SecureStore, and schedule routing complete. Pre-auth and post-auth endpoints verified.
- Gate B: Live and manual attendance flows operational with correct response envelope handling.
- Gate C: Alert/summary/notification flows stable with WebSocket reconnect, close codes (4001/4003), and timezone display verified.
