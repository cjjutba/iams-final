# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <supabase_jwt>`

## Auth Context
All endpoints are protected by Supabase JWT verification middleware (from MOD-01). The middleware checks JWT signature, `is_active = true`, and `email_confirmed_at IS NOT NULL` before the endpoint handler is reached.

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| GET | `/users?role=student&page=1&limit=20` | FUN-02-01 | Admin tools/workflows | Yes (admin) |
| GET | `/users/{id}` | FUN-02-02 | Admin, own-profile retrieval | Yes (admin or own) |
| PATCH | `/users/{id}` | FUN-02-03 | Profile edit flow | Yes (admin or own) |
| DELETE | `/users/{id}` | FUN-02-04 | Admin lifecycle control | Yes (admin) |

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
