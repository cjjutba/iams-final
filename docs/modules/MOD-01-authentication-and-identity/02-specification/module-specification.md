# Module Specification

## Module ID
`MOD-01`

## Purpose
Authenticate students and faculty and protect API access.

## Core Functions
- `FUN-01-01`: Verify student identity by student ID.
- `FUN-01-02`: Register student account after successful identity verification.
- `FUN-01-03`: Login with credentials and issue JWT/access tokens.
- `FUN-01-04`: Refresh access token.
- `FUN-01-05`: Return current authenticated user profile.

## API Contracts
- `POST /auth/verify-student-id`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

## Data Dependencies
- `users`
- University validation data source (CSV/JRMSU import)

## Screen Dependencies
- `SCR-004` StudentLoginScreen
- `SCR-005` FacultyLoginScreen
- `SCR-006` ForgotPasswordScreen
- `SCR-007` StudentRegisterStep1Screen
- `SCR-008` StudentRegisterStep2Screen
- `SCR-010` StudentRegisterReviewScreen

## Done Criteria
- Token lifecycle works (issue, verify, refresh, reject expired).
- Student registration cannot proceed without verified identity.
- Faculty self-registration is blocked in MVP.
- Auth errors follow documented format.
