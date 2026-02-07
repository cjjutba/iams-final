# Capabilities Matrix

| Capability | Function IDs | API/Events | Primary Screens |
|---|---|---|---|
| Faculty auth and restore | FUN-10-01 | `/auth/login`, `/auth/refresh`, `/auth/me` | SCR-005, SCR-006, SCR-019 |
| Faculty schedule + active class | FUN-10-02 | `/schedules/me`, `/attendance/live/{schedule_id}` | SCR-019, SCR-020, SCR-021 |
| Live attendance view | FUN-10-03 | `/attendance/live/{schedule_id}`, `attendance_update` | SCR-021, SCR-022, SCR-023 |
| Manual attendance control | FUN-10-04 | `/attendance/manual`, `/attendance/today` | SCR-024, SCR-021 |
| Early-leave + summary visibility | FUN-10-05 | `/presence/early-leaves`, `/attendance/today`, `session_end`, `early_leave` | SCR-025, SCR-022, SCR-026 |
| Faculty profile + notification feed | FUN-10-06 | `/users/{id}`, `/auth/me`, `WS /ws/{user_id}` | SCR-027, SCR-028, SCR-029 |

## Readiness Gates
- Gate A: Faculty login and schedule routing complete.
- Gate B: Live and manual attendance flows operational.
- Gate C: Alert/summary/notification flows stable with reconnect handling.
