# Module Dependency Order

## Prerequisites Before MOD-09
| Module | Dependency | What MOD-09 Needs |
|---|---|---|
| MOD-01 | Authentication and Identity | JWT login, refresh, verify-student-id, register endpoints |
| MOD-02 | User and Profile Management | Profile PATCH endpoint, user data model |
| MOD-03 | Face Registration and Recognition | Face upload, status check endpoints |
| MOD-05 | Schedules and Enrollments | Schedule list endpoint, enrollment data |
| MOD-06 | Attendance Records | Attendance history, today view endpoints |
| MOD-08 | Realtime Notifications and WebSocket | WebSocket connection with JWT auth, event envelope format |

## Adjacent Modules
| Module | Relationship |
|---|---|
| MOD-02 | User and Profile Management (profile update behavior, deletion impact) |
| MOD-10 | Faculty Mobile App (shared mobile patterns, separate feature scope) |

## Auth Dependencies
- MOD-01 must provide: `POST /auth/login` (pre-auth), `POST /auth/register` (pre-auth), `POST /auth/verify-student-id` (pre-auth), `POST /auth/refresh` (post-auth), `GET /auth/me` (post-auth).
- MOD-08 must provide: `WS /ws/{user_id}?token=<jwt>` with close codes 4001/4003.
- All post-auth endpoints must validate JWT and return 401 on invalid/expired tokens.

## Sequence Note
Implement MOD-09 after core backend contracts are stable enough for mobile integration. All consumed API endpoints must be functional before mobile integration testing.
