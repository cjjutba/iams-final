# Capabilities Matrix

| Capability | Function IDs | Auth Requirement | API/Events | Primary Screens |
|---|---|---|---|---|
| First-run onboarding and role selection | FUN-09-01 | None (local) | local navigation | SCR-001, SCR-002, SCR-003 |
| Student auth + session persistence | FUN-09-02 | Pre-auth → Post-auth | `/auth/login`, `/auth/refresh`, `/auth/me` | SCR-004, SCR-006, SCR-011 |
| Guided registration flow | FUN-09-03 | Pre-auth (Steps 1-2), Post-auth (Steps 3-4) | `/auth/verify-student-id`, `/auth/register`, `/face/register` | SCR-007, SCR-008, SCR-009, SCR-010 |
| Attendance visibility | FUN-09-04 | Post-auth (JWT) | `/attendance/me`, `/schedules/me`, `/attendance/today` | SCR-011, SCR-012, SCR-013, SCR-014 |
| Profile and face maintenance | FUN-09-05 | Post-auth (JWT) | `/auth/me`, `/users/{id}`, `/face/status`, `/face/register` | SCR-015, SCR-016, SCR-017 |
| Notification experience | FUN-09-06 | Post-auth (JWT via query param) | `WS /ws/{user_id}?token=<jwt>` | SCR-018 |

## Per-Screen Auth Map
| Screen Group | Screens | Auth Status |
|---|---|---|
| Onboarding | SCR-001, SCR-002, SCR-003 | Pre-auth (no JWT) |
| Login / Forgot password | SCR-004, SCR-006 | Pre-auth (no JWT) |
| Registration Steps 1-2 | SCR-007, SCR-008 | Pre-auth (no JWT) |
| Registration Steps 3-4 | SCR-009, SCR-010 | Post-auth (JWT from registration) |
| Student portal | SCR-011 to SCR-018 | Post-auth (JWT required) |

## Readiness Gates
- Gate A: Auth + registration flows operational (pre-auth endpoints work without JWT, post-auth endpoints reject without JWT).
- Gate B: Attendance/schedule data renders with proper UI states and timezone-formatted timestamps.
- Gate C: Notification stream updates without restart after reconnect (WebSocket with JWT via `token` query param).
