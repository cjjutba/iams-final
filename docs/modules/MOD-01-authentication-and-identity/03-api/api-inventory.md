# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>`

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| POST | `/auth/verify-student-id` | FUN-01-01 | Student registration step 1 | No |
| POST | `/auth/register` | FUN-01-02 | Student registration review submit | No |
| POST | `/auth/login` | FUN-01-03 | Student login, faculty login | No |
| POST | `/auth/refresh` | FUN-01-04 | Mobile token refresh flow | No (refresh token in payload) |
| GET | `/auth/me` | FUN-01-05 | App startup/session restore/profile fetch | Yes |

## Rate Limits (from technical spec)
- Auth endpoints: 10 requests/minute

## Response Envelope
Success:
```json
{
  "success": true,
  "data": {},
  "message": "Operation completed"
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
