# Endpoint Contract: GET /users

## Function Mapping
- `FUN-02-01`

## Purpose
Return paginated users list with optional role filter.

## Auth
- Header: `Authorization: Bearer <supabase_jwt>`
- Required role: admin

## Query Parameters
| Param | Type | Default | Rules |
|---|---|---|---|
| role | string | (none) | Optional; filter by "student", "faculty", "admin" |
| page | integer | 1 | Min 1 |
| limit | integer | 20 | Min 1, max 100 |

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "email": "student@email.com",
      "first_name": "Juan",
      "last_name": "Dela Cruz",
      "role": "student",
      "student_id": "2024-0001",
      "phone": "09171234567",
      "is_active": true,
      "email_confirmed": true,
      "created_at": "2026-01-15T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}
```

## Error Cases
- `400`: invalid query parameters
- `401`: missing/invalid Supabase JWT
- `403`: caller not authorized (non-admin)

## Caller Context
- Admin-facing operations and scripts.
