# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Base path: `/api/v1/attendance`
- Auth Header: `Authorization: Bearer <token>` (Supabase JWT)

## Auth Context
All MOD-06 endpoints require Supabase JWT. No API key auth (that pattern is for MOD-03/MOD-04 edge devices only).

## Endpoint List
| Method | Path | Function ID | Caller | Role Requirement | Auth Required |
|---|---|---|---|---|---|
| GET | `/attendance/today?schedule_id=uuid` | FUN-06-02 | faculty/class views | faculty or admin | Yes (Supabase JWT) |
| GET | `/attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | FUN-06-03 | student/faculty personal views | any authenticated (role-scoped) | Yes (Supabase JWT) |
| GET | `/attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | FUN-06-04 | faculty/admin reporting | faculty or admin | Yes (Supabase JWT) |
| POST | `/attendance/manual` | FUN-06-05 | faculty manual entry | faculty or admin | Yes (Supabase JWT) |
| GET | `/attendance/live/{schedule_id}` | FUN-06-06 | faculty live monitoring | faculty or admin | Yes (Supabase JWT) |

## Internal Flow Endpoint Context
- FUN-06-01 (Mark Attendance) is invoked by the recognition pipeline/service flow (MOD-03/MOD-07), not a direct public endpoint.

## Response Envelope

### Success
```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

### Error
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```
