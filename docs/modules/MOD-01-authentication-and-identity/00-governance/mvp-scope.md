# MVP Scope

## In Scope
- Student identity verification (registration step 1) — backend endpoint.
- Student account registration after verified identity — backend endpoint; creates Supabase Auth user + local DB record.
- Email verification on registration — Supabase sends confirmation email; backend enforces.
- Student and faculty login — via Supabase client SDK on mobile.
- Token refresh flow — via Supabase client SDK on mobile (automatic).
- Current user endpoint (`/auth/me`) — backend endpoint; JWT-protected.
- Faculty login-only policy with pre-seeded accounts.
- Password reset via email — Supabase client SDK (`resetPasswordForEmail` + `updateUser`).
- Phone number collection during registration (optional, no verification).

## Out of Scope
- Faculty self-registration.
- Admin UI for user management.
- Advanced auth (MFA, OAuth providers).
- Biometric login on mobile device.
- Phone number verification (SMS).

## MVP Auth Provider
**Supabase Auth** is the chosen authentication provider. Mobile uses Supabase client SDK (`@supabase/supabase-js`) for login, token refresh, and password reset. Backend creates users via Supabase Admin API on registration and verifies Supabase-issued JWT on all protected routes.

## MVP Constraints
- Uses university-provided student/faculty data (CSV/JRMSU process).
- Protected routes must validate Supabase JWT and enforce role + is_active + email_confirmed.
- Email confirmation is required before accessing protected resources.

## MVP Gate Criteria
- `FUN-01-01` through `FUN-01-07` implemented and tested.
- Error handling for invalid credentials/token implemented.
- Registration flow blocks unverified students.
- Email verification enforced on protected routes.
- Faculty login works with pre-seeded records only.
- Password reset flow works end-to-end.
