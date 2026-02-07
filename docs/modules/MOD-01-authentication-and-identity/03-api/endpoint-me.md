# Endpoint Contract: GET /auth/me

## Function Mapping
- `FUN-01-05`

## Purpose
Return currently authenticated user profile.

## Header
`Authorization: Bearer <token>`

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "role": "student",
    "student_id": "2024-0001"
  }
}
```

## Error Cases
- `401`: missing/invalid/expired token
- `404`: user not found

## Caller Screens
- `SCR-004` StudentLoginScreen (post-login context)
- `SCR-005` FacultyLoginScreen (post-login context)
- app startup session restore logic
