# API Inventory (Consumed by MOD-09)

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Production: `https://<host>/api/v1` (use `API_BASE_URL` env var)
- Auth Header (post-auth): `Authorization: Bearer <token>`
- All API calls go through backend REST API — mobile does NOT use Supabase JS client SDK directly.

## Response Envelope
Success:
```json
{ "success": true, "data": { ... }, "message": "..." }
```

Error:
```json
{ "success": false, "error": { "code": "...", "message": "..." } }
```
**Note**: Error responses have NO `details` array — only `code` and `message`.

## Consumed Endpoints

### Pre-Auth Endpoints (No JWT Required)
| Method | Path | Used By Function | Purpose |
|---|---|---|---|
| POST | `/auth/verify-student-id` | FUN-09-03 | Registration Step 1 identity verification |
| POST | `/auth/register` | FUN-09-03 | Student account creation (returns tokens) |
| POST | `/auth/login` | FUN-09-02 | Student authentication |

### Post-Auth Endpoints (JWT Required)
| Method | Path | Used By Function | Auth | Purpose |
|---|---|---|---|---|
| POST | `/auth/refresh` | FUN-09-02 | JWT | Session refresh |
| GET | `/auth/me` | FUN-09-02, FUN-09-05 | JWT | Current profile/session user |
| GET | `/schedules/me` | FUN-09-04 | JWT | Student schedule list |
| GET | `/attendance/me?start_date=...&end_date=...` | FUN-09-04 | JWT | Student attendance history |
| GET | `/attendance/today?schedule_id=uuid` | FUN-09-04 | JWT | Per-class today attendance context |
| GET | `/users/{id}` | FUN-09-05 | JWT | Profile fetch |
| PATCH | `/users/{id}` | FUN-09-05 | JWT | Profile updates |
| GET | `/face/status` | FUN-09-05 | JWT | Face registration status |
| POST | `/face/register` | FUN-09-03, FUN-09-05 | JWT | Face registration/re-registration |
| WS | `/ws/{user_id}?token=<jwt>` | FUN-09-06 | JWT (query param) | Student notification stream |

## Timezone Note
All timestamps in API responses use ISO-8601 with +08:00 offset (Asia/Manila). Mobile should format for display accordingly.

## Notes
- Module 9 consumes APIs owned by other modules.
- Any consumed contract change must be reflected in this folder before code updates.
- WebSocket uses JWT via `token` query parameter (not Authorization header) due to WS handshake limitations.
