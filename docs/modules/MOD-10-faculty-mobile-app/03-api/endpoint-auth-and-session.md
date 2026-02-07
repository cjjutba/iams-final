# Endpoint Contract: Auth and Session

## Scope
Endpoints for faculty login, refresh, and current-user retrieval.

## Endpoints
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

## Faculty MVP Constraint
- Faculty self-registration is blocked.
- Faculty accounts are pre-seeded and login-only.

## Client Rules
1. Persist tokens in secure storage.
2. Hydrate auth state before faculty-route rendering.
3. On unauthorized responses, attempt refresh then route to login.
