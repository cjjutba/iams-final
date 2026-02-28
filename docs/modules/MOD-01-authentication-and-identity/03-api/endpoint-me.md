# Endpoint Contract: GET /auth/me

## Function Mapping
- `FUN-01-05`

## Purpose
Return currently authenticated user profile from local database. Verifies Supabase JWT and enforces is_active + email_confirmed.

## Header
`Authorization: Bearer <supabase_jwt>`

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
    "email_confirmed": true
  }
}
```

## Backend Process
1. Validate Supabase JWT signature using JWT secret from environment.
2. Extract `sub` (user ID) from JWT claims.
3. Load user profile from local `users` table.
4. Check `is_active = true`.
5. Check `email_confirmed_at IS NOT NULL`.
6. Return profile payload (excluding sensitive fields).

## Error Cases
- `401`: missing/invalid/expired Supabase JWT
- `403`: user is inactive (`is_active = false`) or email not confirmed (`email_confirmed_at IS NULL`)
- `404`: user not found in local `users` table

## Caller Screens
- `SCR-004` StudentLoginScreen (post-login session restore)
- `SCR-005` FacultyLoginScreen (post-login session restore)
- App startup session restore logic
