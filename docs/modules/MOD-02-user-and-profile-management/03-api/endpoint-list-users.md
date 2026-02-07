# Endpoint Contract: GET /users?role=student&page=1&limit=20

## Function Mapping
- `FUN-02-01`

## Purpose
Return paginated users list with optional role filter.

## Query Parameters
- `role` (optional)
- `page` (default 1)
- `limit` (default 20)

## Success Response
```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}
```

## Error Cases
- `400`: invalid query parameters
- `401`: missing/invalid token
- `403`: caller not authorized (non-admin)

## Caller Context
- Admin-facing operations and scripts.
