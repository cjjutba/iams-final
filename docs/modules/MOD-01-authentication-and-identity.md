# MOD-01: Authentication and Identity

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Authenticate students and faculty and protect API access.

Functions:
- `FUN-01-01`: Verify student identity by student ID.
- `FUN-01-02`: Register student account after successful identity verification.
- `FUN-01-03`: Login with credentials and issue JWT/access tokens.
- `FUN-01-04`: Refresh access token.
- `FUN-01-05`: Return current authenticated user profile.

API Contracts:
- `POST /auth/verify-student-id`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

Data:
- `users`
- University validation data source (CSV/JRMSU import)

Screens:
- `SCR-004` StudentLoginScreen
- `SCR-005` FacultyLoginScreen
- `SCR-006` ForgotPasswordScreen
- `SCR-007` StudentRegisterStep1Screen
- `SCR-008` StudentRegisterStep2Screen
- `SCR-010` StudentRegisterReviewScreen

Done Criteria:
- Token lifecycle works (issue, verify, refresh, reject expired).
- Student registration cannot proceed without verified identity.
- Faculty self-registration is blocked in MVP.
- Auth errors follow documented format.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
