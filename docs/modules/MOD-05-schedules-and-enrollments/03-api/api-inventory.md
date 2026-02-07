# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>` for protected routes

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| GET | `/schedules?day=1` | FUN-05-01 | student/faculty/admin flows | Yes |
| GET | `/schedules/{id}` | FUN-05-02 | schedule detail consumers | Yes |
| POST | `/schedules` | FUN-05-03 | admin schedule setup | Yes |
| GET | `/schedules/me` | FUN-05-04 | student/faculty app flows | Yes |
| GET | `/schedules/{id}/students` | FUN-05-05 | roster and class detail flows | Yes |

## Response Envelope
Success:
```json
{
  "success": true,
  "data": {}
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
