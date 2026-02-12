# Endpoint Contract: Auth and Session

## Scope
Endpoints for faculty login, refresh, and current-user retrieval.

## Endpoints
| Endpoint | Method | Auth |
|---|---|---|
| `/auth/login` | POST | Pre-auth |
| `/auth/forgot-password` | POST | Pre-auth |
| `/auth/refresh` | POST | Post-auth |
| `/auth/me` | GET | Post-auth |

## Faculty MVP Constraint
- Faculty self-registration is blocked.
- Faculty accounts are pre-seeded and login-only.

## Login Request/Response Example

**Request** (pre-auth, no JWT):
```json
POST /api/v1/auth/login
{
  "email": "faculty@gmail.com",
  "password": "password123"
}
```

**Success Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "user": {
      "id": "uuid",
      "email": "faculty@gmail.com",
      "role": "faculty",
      "first_name": "Faculty",
      "last_name": "User"
    }
  }
}
```

**Error Response** (no `details` array):
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password"
  }
}
```

## Client Rules
1. Persist tokens in Expo SecureStore (never AsyncStorage).
2. Hydrate auth state from SecureStore before faculty-route rendering.
3. On 401 response, attempt refresh via `POST /auth/refresh` then route to login if refresh fails.
4. Parse response envelope without assuming `details` array.
