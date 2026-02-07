# API Inventory (Consumed by MOD-10)

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>`

## Consumed Endpoints
| Method | Path | Used By Function | Purpose |
|---|---|---|---|
| POST | `/auth/login` | FUN-10-01 | Faculty authentication |
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
| WS | `/ws/{user_id}` | FUN-10-03, FUN-10-05, FUN-10-06 | Realtime updates and notifications |

## Notes
- Module 10 consumes APIs owned by backend modules and does not define new backend endpoints.
