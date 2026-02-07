# Endpoint Contract: Auth and Session

## Scope
Endpoints for student login, refresh, and current-user retrieval.

## Endpoints
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

## Login Request (Example)
```json
{
  "email": "student@email.com",
  "password": "securepassword"
}
```

## Login Success Payload (Example)
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

## Client Rules
1. Persist tokens in secure storage.
2. Hydrate auth state before protected-screen rendering.
3. On 401/expired token, attempt refresh then fallback to login.
