# Endpoint Contract: POST /auth/verify-student-id

## Function Mapping
- `FUN-01-01`

## Purpose
Validate student identity before account creation.

## Request
```json
{
  "student_id": "2024-0001"
}
```

## Success Response (Valid)
```json
{
  "success": true,
  "data": {
    "valid": true,
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "course": "BS Computer Engineering",
    "year": "3rd Year",
    "section": "CPE-3A",
    "email": "juandelacruz@email.com"
  }
}
```

## Success Response (Invalid)
```json
{
  "success": true,
  "data": {
    "valid": false
  }
}
```

## Error Cases
- `400`: invalid input format
- `500`: internal lookup/service error

## Caller Screens
- `SCR-007` StudentRegisterStep1Screen
