# Error Models

## Standard Error Shape
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": []
  }
}
```

## User-Related Codes
- `VALIDATION_ERROR` — invalid payload, immutable field change attempt (email)
- `UNAUTHORIZED` — missing or invalid Supabase JWT
- `FORBIDDEN` — role/ownership check failed
- `NOT_FOUND` — user ID not found
- `SERVER_ERROR` — unexpected error (e.g., Supabase Auth deletion failure)

## Status Mapping
| Status | Typical User/Profile Scenario |
|---|---|
| 400 | Invalid payload, query params, or immutable field change (email) |
| 401 | Missing or invalid Supabase JWT |
| 403 | Unauthorized role/action (non-admin on restricted field or another user's record) |
| 404 | User ID not found |
| 500 | Unexpected server error or Supabase Auth operation failure |

## Error Scenarios by Function

### FUN-02-01 List Users
- `400`: invalid page/limit params
- `401`: no JWT
- `403`: non-admin caller

### FUN-02-02 Get User
- `401`: no JWT
- `403`: non-admin requesting another user
- `404`: user not found

### FUN-02-03 Update User
- `400`: invalid payload, email change attempt
- `401`: no JWT
- `403`: non-admin changing restricted fields, or non-owner
- `404`: user not found

### FUN-02-04 Delete User
- `401`: no JWT
- `403`: non-admin caller
- `404`: user not found
- `500`: Supabase Auth deletion failure
