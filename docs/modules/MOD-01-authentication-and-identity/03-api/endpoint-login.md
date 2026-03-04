# Supabase Client Operation: Login

## Function Mapping
- `FUN-01-03`

## Implementation
**Not a backend endpoint.** Login is handled by Supabase client SDK on mobile.

## Supabase SDK Call
```typescript
const { data, error } = await supabase.auth.signInWithPassword({
  email: "student@email.com",
  password: "securepassword"
})
```

## Supabase Session Response
```json
{
  "access_token": "supabase_jwt",
  "refresh_token": "refresh_token",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "student@email.com",
    "email_confirmed_at": "2024-01-15T10:00:00Z"
  }
}
```

## Post-Login Backend Validation
After Supabase login, mobile calls `GET /auth/me` with Supabase JWT. Backend middleware checks:
- JWT signature validity
- `is_active = true` in local `users` table
- `email_confirmed_at IS NOT NULL` in local `users` table

## Error Cases (Supabase Client)
- Invalid credentials: Supabase returns `AuthApiError` with "Invalid login credentials"
- Email not confirmed: Supabase may return error depending on project settings

## Error Cases (Backend — on `GET /auth/me` after login)
- `401`: invalid/expired JWT
- `403`: inactive account or email not confirmed

## Caller Screens
- `SCR-004` StudentLoginScreen
- `SCR-005` FacultyLoginScreen
