# Endpoint Contract: Profile and Face Management

## Scope
Endpoints for profile management and face re-registration.

## Endpoints
| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /auth/me` | Post-auth (JWT) | Current user profile |
| `GET /users/{id}` | Post-auth (JWT) | Profile detail (optional path) |
| `PATCH /users/{id}` | Post-auth (JWT) | Profile updates |
| `GET /face/status` | Post-auth (JWT) | Face registration status |
| `POST /face/register` | Post-auth (JWT) | Face re-registration |

**All endpoints require `Authorization: Bearer <token>` header.**

## Profile Update Request
```json
PATCH /api/v1/users/{id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "first_name": "Chris",
  "last_name": "Jutba",
  "email": "newemail@example.com"
}
```

### Profile Update Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "newemail@example.com",
    "first_name": "Chris",
    "last_name": "Jutba",
    "role": "student"
  },
  "message": "Profile updated successfully"
}
```

## Face Status Check
```
GET /api/v1/face/status
Authorization: Bearer <access_token>
```

## Face Re-Registration
```
POST /api/v1/face/register
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

images: [file1, file2, file3, ...]  (3-5 images)
```

## Service Method Notes
- `authService.updateProfile(userId, data)` — userId is required as first argument.
- `authService.changePassword(oldPassword, newPassword)` — two separate string arguments, not an object.

## Client Rules
- Profile edits must be validated before submit.
- Face re-registration uses same quality and count constraints as initial registration (3-5 images).
- Show clear status feedback after profile or face update success/failure.
- On 401: attempt refresh, fallback to login.

## Screens
- `SCR-015` StudentProfileScreen
- `SCR-016` StudentEditProfileScreen
- `SCR-017` StudentFaceReregisterScreen
