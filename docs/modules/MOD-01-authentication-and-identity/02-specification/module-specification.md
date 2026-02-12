# Module Specification

## Module ID
`MOD-01`

## Purpose
Authenticate students and faculty and protect API access using Supabase Auth as the authentication provider.

## Auth Provider
**Supabase Auth** — Mobile uses Supabase client SDK for login, token refresh, and password reset. Backend creates users via Supabase Admin API on registration and verifies Supabase-issued JWT on all protected routes.

## Core Functions
- `FUN-01-01`: Verify student identity by student ID (backend endpoint).
- `FUN-01-02`: Register student account after successful identity verification (backend endpoint; creates Supabase Auth user + local DB record; triggers email verification).
- `FUN-01-03`: Login with credentials via Supabase client SDK on mobile.
- `FUN-01-04`: Refresh access token via Supabase client SDK on mobile (automatic).
- `FUN-01-05`: Return current authenticated user profile (backend endpoint; JWT-protected).
- `FUN-01-06`: Request password reset via Supabase client SDK on mobile.
- `FUN-01-07`: Complete password reset via Supabase client SDK on mobile.

## API Contracts (Backend Endpoints)
- `POST /auth/verify-student-id` (FUN-01-01)
- `POST /auth/register` (FUN-01-02)
- `GET /auth/me` (FUN-01-05)

## Supabase Client Operations (Mobile)
- `supabase.auth.signInWithPassword()` (FUN-01-03)
- `supabase.auth.refreshSession()` (FUN-01-04)
- `supabase.auth.resetPasswordForEmail()` (FUN-01-06)
- `supabase.auth.updateUser({ password })` (FUN-01-07)

## Supabase Automatic
- Email verification on registration (confirmation email sent by Supabase)

## Data Dependencies
- `users` table (local PostgreSQL via Supabase)
- University validation data source (CSV/JRMSU import)
- Supabase Auth user records

## Screen Dependencies
- `SCR-004` StudentLoginScreen
- `SCR-005` FacultyLoginScreen
- `SCR-006` ForgotPasswordScreen
- `SCR-007` StudentRegisterStep1Screen
- `SCR-008` StudentRegisterStep2Screen
- `SCR-010` StudentRegisterReviewScreen
- `SCR-NEW` EmailVerificationPendingScreen (post-registration; instructs user to check email)

## Done Criteria
- Token lifecycle works: Supabase issues JWT on login, backend verifies, refresh works automatically.
- Student registration creates Supabase Auth user + local DB record and triggers email verification.
- Email verification is enforced: unverified users cannot access protected resources.
- Student registration cannot proceed without verified identity.
- Faculty self-registration is blocked in MVP.
- Password reset flow works via Supabase client.
- Auth errors follow documented format.
