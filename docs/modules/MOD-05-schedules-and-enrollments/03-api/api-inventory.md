# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Base path: `/api/v1/schedules`
- Auth: Supabase JWT (`Authorization: Bearer <token>`) on all endpoints

## Auth Context
All MOD-05 endpoints require Supabase JWT. No API key auth (that pattern is for edge devices in MOD-03/MOD-04).

## Endpoint List
| Method | Path | Function ID | Caller | Auth | Role Requirement |
|---|---|---|---|---|---|
| GET | `/schedules?day=1` | FUN-05-01 | student/faculty/admin | Supabase JWT | all roles |
| GET | `/schedules/{id}` | FUN-05-02 | schedule detail consumers | Supabase JWT | all roles |
| POST | `/schedules` | FUN-05-03 | admin schedule setup | Supabase JWT | admin only |
| GET | `/schedules/me` | FUN-05-04 | student/faculty app flows | Supabase JWT | student/faculty |
| GET | `/schedules/{id}/students` | FUN-05-05 | roster and class detail flows | Supabase JWT | admin/assigned faculty/enrolled student |

## Response Envelope
Success:
```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

Error:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```
