# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <token>`

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| GET | `/users?role=student&page=1&limit=20` | FUN-02-01 | Admin tools/workflows | Yes |
| GET | `/users/{id}` | FUN-02-02 | Admin, own-profile retrieval | Yes |
| PATCH | `/users/{id}` | FUN-02-03 | Profile edit flow | Yes |
| DELETE | `/users/{id}` | FUN-02-04 | Admin lifecycle control | Yes |

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
