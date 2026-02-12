# Endpoint Contract: Auth and Session

## Scope
Endpoints for student login, refresh, and current-user retrieval.

## Endpoints
| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /auth/login` | Pre-auth (no JWT) | Student authentication |
| `POST /auth/refresh` | Post-auth (JWT) | Token refresh |
| `GET /auth/me` | Post-auth (JWT) | Current user profile |

## Login Request
```json
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "student@email.com",
  "password": "securepassword"
}
```
**Auth**: No JWT required (pre-auth endpoint).

## Login Success Response
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

## Login Error Response
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password"
  }
}
```
**Note**: No `details` array in error responses.

## Get Current User
```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```
**Auth**: Post-auth (JWT required).

## Refresh Token
```json
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```
**Auth**: Post-auth (requires valid refresh token).

## Client Rules
1. Persist tokens in Expo SecureStore (never AsyncStorage).
2. Hydrate auth state from SecureStore before protected-screen rendering.
3. On 401/expired token: attempt refresh, then fallback to login.
4. Never log token values to console.
