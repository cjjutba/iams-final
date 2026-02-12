# Implementation Plan (MOD-01)

## Phase 1: Foundations
- Set up Supabase project (Auth + PostgreSQL + email templates + redirect URLs).
- Configure auth env variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`).
- Implement Supabase JWT verification middleware for FastAPI (backend auth dependency).
- Ensure users repository/table access is available (including phone, email_confirmed_at columns).

## Phase 2: Identity + Registration
- Implement `FUN-01-01` student identity verification (backend endpoint).
- Implement `FUN-01-02` registration gating and account creation:
  - Backend creates Supabase Auth user via Admin API.
  - Backend inserts local `users` table record.
  - Supabase sends email verification automatically.
  - Include phone field (optional) in registration payload.

## Phase 3: Session Auth + Profile
- Implement `FUN-01-05` current user endpoint (`GET /auth/me`):
  - Verify Supabase JWT.
  - Enforce is_active and email_confirmed checks.
  - Return profile with phone and email_confirmed fields.
- Configure email_confirmed_at sync from Supabase Auth to local DB.

## Phase 4: Mobile Auth Integration
- Set up Supabase client SDK in React Native app (`@supabase/supabase-js`).
- Implement `FUN-01-03` login via Supabase client on mobile screens.
- Implement `FUN-01-04` automatic token refresh via Supabase client.
- Implement `FUN-01-06` + `FUN-01-07` password reset flow on mobile.
- Wire auth screens to API contracts (backend endpoints + Supabase client).
- Add session persistence and restore behavior (Supabase client `onAuthStateChange`).
- Implement EmailVerificationPendingScreen (post-registration).
- Implement deep link handling for password reset.

## Phase 5: Validation
- Run unit, integration, and E2E auth tests (see test-cases.md).
- Validate acceptance criteria (see acceptance-criteria.md).
- Test email verification flow end-to-end.
- Test password reset flow end-to-end.
- Test rate limiting on backend endpoints.
- Update traceability matrix.
