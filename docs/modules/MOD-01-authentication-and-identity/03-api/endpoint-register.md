# Endpoint Contract: POST /auth/register

## Function Mapping
- `FUN-01-02`

## Purpose
Create student account after identity verification. Backend creates user in Supabase Auth (via Admin API) and inserts profile into local `users` table. Supabase sends email verification automatically.

## Request
```json
{
  "email": "student@email.com",
  "password": "securepassword",
  "first_name": "Juan",
  "last_name": "Dela Cruz",
  "role": "student",
  "student_id": "2024-0001",
  "phone": "09171234567"
}
```

### Field Rules
| Field | Required | Validation |
|---|---|---|
| email | Yes | Valid email format; unique in system |
| password | Yes | Min 8 characters |
| first_name | Yes | Non-empty string |
| last_name | Yes | Non-empty string |
| role | Yes | Must be `student` (MVP) |
| student_id | Yes | Must match verified identity in university dataset |
| phone | No | Optional contact number; no verification required |

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "role": "student"
  },
  "message": "Account created. Please check your email to verify your account."
}
```

## Backend Process
1. Validate request payload and field rules.
2. Re-verify student_id against university dataset.
3. Check email and student_id uniqueness in local DB.
4. Create user in Supabase Auth via Admin API (`supabase.auth.admin.createUser()`).
5. Insert user profile into local `users` table (with `email_confirmed_at = null`).
6. Supabase sends confirmation email to the provided email address.
7. Return `201` with user metadata.

## Error Cases
- `400`: validation failure (invalid payload, weak password, invalid email format)
- `409`: duplicate email or student_id already registered
- `403`: role or policy violation (non-student role, unverified student_id, faculty self-registration attempt)
- `500`: Supabase Auth or database error

## Caller Screens
- `SCR-010` StudentRegisterReviewScreen
