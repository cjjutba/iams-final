# API Inventory (Consumed by MOD-10)

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Production: `https://<domain>/api/v1`
- Auth Header: `Authorization: Bearer <token>` (post-auth endpoints only)

## Response Envelope

**Success:**
```json
{ "success": true, "data": { ... }, "message": "..." }
```

**Error:**
```json
{ "success": false, "error": { "code": "ERROR_CODE", "message": "..." } }
```

> **Important:** Error responses do NOT contain a `details` array. Do not assume one exists.

## Pre-Auth Endpoints (No JWT Required)
| Method | Path | Used By Function | Purpose |
|---|---|---|---|
| POST | `/auth/login` | FUN-10-01 | Faculty authentication |
| POST | `/auth/forgot-password` | FUN-10-01 | Password reset request |

## Post-Auth Endpoints (JWT Required)
| Method | Path | Used By Function | Purpose |
|---|---|---|---|
| POST | `/auth/refresh` | FUN-10-01 | Session refresh |
| GET | `/auth/me` | FUN-10-01, FUN-10-06 | Current user/profile context |
| GET | `/schedules/me` | FUN-10-02 | Faculty schedule list |
| GET | `/schedules/{id}/students` | FUN-10-02, FUN-10-03 | Class roster context |
| GET | `/attendance/live/{schedule_id}` | FUN-10-03 | Live attendance roster |
| GET | `/attendance/today?schedule_id=uuid` | FUN-10-03, FUN-10-05 | Today summary/records context |
| POST | `/attendance/manual` | FUN-10-04 | Manual attendance updates |
| GET | `/presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` | FUN-10-05 | Early-leave alert list |
| GET | `/presence/{attendance_id}/logs` | FUN-10-05 | Student-level presence log detail |
| GET | `/attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | FUN-10-05 | Class summary/history data |
| GET | `/users/{id}` | FUN-10-06 | Faculty profile fetch |
| PATCH | `/users/{id}` | FUN-10-06 | Faculty profile update |
| WS | `/ws/{user_id}?token=<jwt>` | FUN-10-03, FUN-10-05, FUN-10-06 | Realtime updates (JWT via query param) |

## Timezone Note
- All timestamp fields use ISO-8601 with `+08:00` offset (Asia/Manila).
- Date filter parameters use `YYYY-MM-DD` format.

## Notes
- Module 10 consumes APIs owned by backend modules and does not define new backend endpoints.
- Mobile does NOT use Supabase JS client SDK — all auth is via backend-issued JWT.
