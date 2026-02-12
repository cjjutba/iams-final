# Faculty Mobile Catalog

## Module Summary
- Module ID: `MOD-10`
- Module Name: Faculty Mobile App
- Primary Domain: Mobile

## Auth Context
Faculty login (SCR-005) is the only pre-auth entry point. All portal screens (SCR-019 to SCR-029) require a backend-issued JWT. Faculty accounts are pre-seeded — no self-registration.

## Function Catalog
| Function ID | Function Name | Auth Type | Brief Description |
|---|---|---|---|
| FUN-10-01 | Faculty login and session restore | Pre-auth → Post-auth | Authenticate faculty users and restore active session safely. |
| FUN-10-02 | View schedule and active class | Post-auth | Present teaching schedule and active class context. |
| FUN-10-03 | Live attendance monitoring | Post-auth + WebSocket | Display realtime attendance roster and scan updates. |
| FUN-10-04 | Manual attendance updates | Post-auth | Allow faculty correction/override of attendance records. |
| FUN-10-05 | Early-leave alerts and class summaries | Post-auth + WebSocket | Show in-session alerts and post-session class summary views. |
| FUN-10-06 | Faculty profile and notifications | Post-auth + WebSocket | Manage profile details and view notification feed. |

## Screen Domains
- Pre-auth: `SCR-005`, `SCR-006`
- Post-auth: `SCR-019` to `SCR-029`

## Consumed API Summary
| API Group | Auth Requirement | Endpoints |
|---|---|---|
| Auth | Pre-auth (login, forgot-password) / Post-auth (refresh, me) | `/auth/login`, `/auth/forgot-password`, `/auth/refresh`, `/auth/me` |
| Schedules | Post-auth | `/schedules/me`, `/schedules/{id}/students` |
| Attendance | Post-auth | `/attendance/live/{schedule_id}`, `/attendance/today`, `/attendance/manual`, `/attendance` |
| Presence | Post-auth | `/presence/early-leaves`, `/presence/{attendance_id}/logs` |
| Profile | Post-auth | `/users/{id}` (GET, PATCH) |
| WebSocket | Post-auth (JWT via query param) | `WS /ws/{user_id}?token=<jwt>` |
