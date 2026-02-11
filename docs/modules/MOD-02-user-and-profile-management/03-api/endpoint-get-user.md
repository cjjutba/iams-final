# Endpoint Contract: GET /users/{id}

## Function Mapping
- `FUN-02-02`

## Purpose
Return one user record by user ID.

## Auth
- Header: `Authorization: Bearer <supabase_jwt>`
- Required: admin or own record (JWT `sub` matches path `id`)

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
    "role": "student",
    "student_id": "2024-0001",
    "phone": "09171234567",
    "is_active": true,
    "email_confirmed": true,
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

## Error Cases
- `401`: missing/invalid Supabase JWT
- `403`: unauthorized access (non-admin requesting another user's record)
- `404`: user not found

## Caller Screens
- `SCR-015` StudentProfileScreen
- `SCR-027` FacultyProfileScreen
