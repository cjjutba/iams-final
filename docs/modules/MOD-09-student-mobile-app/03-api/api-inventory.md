# API Inventory (Consumed by MOD-09)

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>`

## Consumed Endpoints
| Method | Path | Used By Function | Purpose |
|---|---|---|---|
| POST | `/auth/verify-student-id` | FUN-09-03 | Registration Step 1 identity verification |
| POST | `/auth/register` | FUN-09-03 | Student account creation |
| POST | `/auth/login` | FUN-09-02 | Student authentication |
| POST | `/auth/refresh` | FUN-09-02 | Session refresh |
| GET | `/auth/me` | FUN-09-02, FUN-09-05 | Current profile/session user |
| GET | `/schedules/me` | FUN-09-04 | Student schedule list |
| GET | `/attendance/me?start_date=...&end_date=...` | FUN-09-04 | Student attendance history |
| GET | `/attendance/today?schedule_id=uuid` | FUN-09-04 | Per-class today attendance context |
| GET | `/users/{id}` | FUN-09-05 | Profile fetch (optional based on backend design) |
| PATCH | `/users/{id}` | FUN-09-05 | Profile updates |
| GET | `/face/status` | FUN-09-05 | Face registration status |
| POST | `/face/register` | FUN-09-03, FUN-09-05 | Face registration/re-registration |
| WS | `/ws/{user_id}` | FUN-09-06 | Student notification stream |

## Notes
- Module 9 consumes APIs owned by other modules.
- Any consumed contract change must be reflected in this folder before code updates.
