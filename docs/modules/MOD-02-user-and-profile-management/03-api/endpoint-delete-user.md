# Endpoint Contract: DELETE /users/{id}

## Function Mapping
- `FUN-02-04`

## Purpose
Delete or deactivate user with safe lifecycle behavior.

## Path Parameter
- `id` (UUID)

## Success Response
```json
{
  "success": true,
  "message": "User deleted"
}
```

## Error Cases
- `401`: missing/invalid token
- `403`: unauthorized caller (non-admin)
- `404`: user not found
- `409`: conflict due to unresolved dependency state (if enforced)

## Caller Context
- Admin lifecycle operations and scripts.
