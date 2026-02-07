# Endpoint Contract: GET /users/{id}

## Function Mapping
- `FUN-02-02`

## Purpose
Return one user record by user ID.

## Path Parameter
- `id` (UUID)

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "role": "student"
  }
}
```

## Error Cases
- `401`: missing/invalid token
- `403`: unauthorized access
- `404`: user not found

## Caller Screens
- `SCR-015` StudentProfileScreen
- `SCR-027` FacultyProfileScreen
