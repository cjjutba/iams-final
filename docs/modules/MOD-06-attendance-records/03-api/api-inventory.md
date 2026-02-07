# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>`

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| GET | `/attendance/today?schedule_id=uuid` | FUN-06-02 | faculty/class views | Yes |
| GET | `/attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | FUN-06-03 | student history views | Yes |
| GET | `/attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | FUN-06-04 | faculty/admin reporting | Yes |
| POST | `/attendance/manual` | FUN-06-05 | faculty manual entry | Yes |
| GET | `/attendance/live/{schedule_id}` | FUN-06-06 | faculty live monitoring | Yes |

## Internal Flow Endpoint Context
- FUN-06-01 is typically invoked by recognition pipeline/service flow, not direct public endpoint in current docs.
