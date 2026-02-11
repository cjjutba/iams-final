# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header: `Authorization: Bearer <supabase_jwt>`
- Auth Provider: **Supabase Auth**

## Backend Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| POST | `/auth/verify-student-id` | FUN-01-01 | Student registration step 1 | No |
| POST | `/auth/register` | FUN-01-02 | Student registration review submit | No |
| GET | `/auth/me` | FUN-01-05 | App startup/session restore/profile fetch | Yes (Supabase JWT) |

## Supabase Client Operations (Mobile — no backend endpoint)
| Operation | Supabase SDK Method | Function ID | Caller |
|---|---|---|---|
| Login | `supabase.auth.signInWithPassword()` | FUN-01-03 | StudentLoginScreen, FacultyLoginScreen |
| Token Refresh | `supabase.auth.refreshSession()` | FUN-01-04 | Automatic (Supabase client) |
| Request Password Reset | `supabase.auth.resetPasswordForEmail()` | FUN-01-06 | ForgotPasswordScreen |
| Complete Password Reset | `supabase.auth.updateUser({ password })` | FUN-01-07 | Password reset deep link handler |

## Supabase Automatic
| Operation | Trigger | Notes |
|---|---|---|
| Email Verification | User creation via `POST /auth/register` | Supabase sends confirmation email |

## Rate Limits (from technical spec)
- Backend auth endpoints: 10 requests/minute

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
