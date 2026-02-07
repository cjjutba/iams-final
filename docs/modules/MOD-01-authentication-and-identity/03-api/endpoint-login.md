# Endpoint Contract: POST /auth/login

## Function Mapping
- `FUN-01-03`

## Purpose
Authenticate user credentials and issue tokens.

## Request
```json
{
  "email": "student@email.com",
  "password": "securepassword"
}
```

## Success Response
```json
{
  "success": true,
  "data": {
    "access_token": "jwt_token",
    "refresh_token": "refresh_token",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

## Error Cases
- `401`: invalid credentials
- `403`: inactive account / forbidden policy
- `500`: authentication service error

## Caller Screens
- `SCR-004` StudentLoginScreen
- `SCR-005` FacultyLoginScreen
