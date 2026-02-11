# Endpoint Contract: PATCH /users/{id}

## Function Mapping
- `FUN-02-03`

## Purpose
Update allowed user profile fields.

## Auth
- Header: `Authorization: Bearer <supabase_jwt>`
- Required: admin or own record (JWT `sub` matches path `id`)

## Path Parameter
- `id` (UUID)

## Field Rules
| Field | Student/Faculty (Own) | Admin | Notes |
|---|---|---|---|
| first_name | Editable | Editable | Max 100 chars |
| last_name | Editable | Editable | Max 100 chars |
| phone | Editable | Editable | Max 20 chars, optional |
| email | Rejected (immutable) | Rejected (immutable) | Always returns `400` |
| role | Rejected (`403`) | Editable | student, faculty, admin |
| student_id | Rejected (`403`) | Editable | Must remain unique |
| is_active | Rejected (`403`) | Editable | true/false |

## Request Example (Student/Faculty)
```json
{
  "first_name": "Updated Name",
  "phone": "09179876543"
}
```

## Request Example (Admin — Restricted Fields)
```json
{
  "role": "faculty",
  "is_active": false
}
```

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "first_name": "Updated Name",
    "last_name": "Dela Cruz",
    "role": "student",
    "student_id": "2024-0001",
    "phone": "09179876543",
    "is_active": true,
    "email_confirmed": true,
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

## Error Cases
- `400`: invalid payload, restricted field update (email), invalid format
- `401`: missing/invalid Supabase JWT
- `403`: unauthorized update attempt (non-admin changing restricted fields, or non-owner)
- `404`: user not found

## Caller Screens
- `SCR-016` StudentEditProfileScreen
- `SCR-028` FacultyEditProfileScreen
