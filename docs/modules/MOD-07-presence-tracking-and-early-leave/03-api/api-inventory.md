# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>`

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| GET | `/presence/{attendance_id}/logs` | FUN-07-06 | faculty/detail views | Yes |
| GET | `/presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` | FUN-07-06 | faculty alert views | Yes |

## Internal Function Flow Context
- FUN-07-01..FUN-07-05 are internal service behaviors driving log/event generation.
