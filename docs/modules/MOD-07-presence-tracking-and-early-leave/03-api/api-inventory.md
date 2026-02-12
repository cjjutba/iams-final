# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Base path: `/api/v1/presence`
- Auth Header: `Authorization: Bearer <token>` (Supabase JWT)

## Auth Context
All MOD-07 user-facing endpoints require Supabase JWT. No API key auth (that pattern is for MOD-03/MOD-04 edge devices only).

Role-based access:
- **GET /presence/{attendance_id}/logs** — faculty or admin.
- **GET /presence/early-leaves** — faculty or admin.

Responses:
- 401 for missing/invalid JWT.
- 403 for insufficient role (student attempting faculty-only endpoint).

## Endpoint List
| Method | Path | Function ID | Caller | Role Requirement | Auth Required |
|---|---|---|---|---|---|
| GET | `/presence/{attendance_id}/logs` | FUN-07-06 | faculty/detail views | faculty or admin | Yes (Supabase JWT) |
| GET | `/presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` | FUN-07-06 | faculty alert views | faculty or admin | Yes (Supabase JWT) |

## Internal Function Flow Context
- FUN-07-01 to FUN-07-05 are **system-internal** service behaviors driving log/event generation — no HTTP endpoints.

## Response Envelope
Success:
```json
{
  "success": true,
  "data": {},
  "message": "Description of result"
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
Note: No `details` array in error responses (consistent with MOD-01 through MOD-06).
