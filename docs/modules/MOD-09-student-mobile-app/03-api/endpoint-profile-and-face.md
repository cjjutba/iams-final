# Endpoint Contract: Profile and Face Management

## Scope
Endpoints for profile management and face re-registration.

## Endpoints
- `GET /auth/me`
- `GET /users/{id}` (optional profile detail path)
- `PATCH /users/{id}`
- `GET /face/status`
- `POST /face/register`

## Client Rules
- Profile edits must be validated before submit.
- Face re-registration uses same quality and count constraints as registration.
- Show clear status feedback after profile or face update success/failure.

## Screens
- `SCR-015` StudentProfileScreen
- `SCR-016` StudentEditProfileScreen
- `SCR-017` StudentFaceReregisterScreen
