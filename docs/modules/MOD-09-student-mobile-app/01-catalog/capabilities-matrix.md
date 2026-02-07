# Capabilities Matrix

| Capability | Function IDs | API/Events | Primary Screens |
|---|---|---|---|
| First-run onboarding and role selection | FUN-09-01 | local navigation | SCR-001, SCR-002, SCR-003 |
| Student auth + session persistence | FUN-09-02 | `/auth/login`, `/auth/refresh`, `/auth/me` | SCR-004, SCR-011 |
| Guided registration flow | FUN-09-03 | `/auth/verify-student-id`, `/auth/register`, `/face/register` | SCR-007, SCR-008, SCR-009, SCR-010 |
| Attendance visibility | FUN-09-04 | `/attendance/me`, `/schedules/me`, optional `/attendance/today` | SCR-011, SCR-012, SCR-013, SCR-014 |
| Profile and face maintenance | FUN-09-05 | `/auth/me`, `/users/{id}`, `/face/status`, `/face/register` | SCR-015, SCR-016, SCR-017 |
| Notification experience | FUN-09-06 | `WS /ws/{user_id}` + events | SCR-018 |

## Readiness Gates
- Gate A: auth + registration flows operational.
- Gate B: attendance/schedule data renders with proper UI states.
- Gate C: notification stream updates without restart after reconnect.
