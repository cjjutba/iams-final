# Endpoint Contract: POST /auth/register

## Function Mapping
- `FUN-01-02`

## Purpose
Create student account after identity verification.

## Request
```json
{
  "email": "student@email.com",
  "password": "securepassword",
  "first_name": "Juan",
  "last_name": "Dela Cruz",
  "role": "student",
  "student_id": "2024-0001"
}
```

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "role": "student"
  }
}
```

## Error Cases
- `400`: validation failure (duplicate email, invalid payload)
- `403`: role or policy violation
- `500`: account creation failure

## Caller Screens
- `SCR-010` StudentRegisterReviewScreen
