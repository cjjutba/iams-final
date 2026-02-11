# Changelog (MOD-01 Docs)

## 2026-02-12
- **Auth provider decision:** Declared Supabase Auth as the authentication provider for MOD-01.
- **Functions expanded:** Extended function range from FUN-01-01–FUN-01-05 to FUN-01-01–FUN-01-07 (added FUN-01-06 Request Password Reset, FUN-01-07 Complete Password Reset).
- **Architecture split:** Separated auth into Backend Endpoints (verify-student-id, register, me) and Supabase Client Operations (login, token refresh, password reset request, password reset completion).
- **Removed backend login/refresh endpoints:** POST /auth/login and POST /auth/refresh replaced by Supabase client SDK operations on mobile.
- **Email verification added:** Supabase sends confirmation email on registration; backend enforces `email_confirmed_at IS NOT NULL` on protected routes.
- **Password reset flow added:** Full password reset via Supabase client SDK (`resetPasswordForEmail` + `updateUser`) with deep link handling.
- **Phone field added:** Optional `phone VARCHAR(20)` column added to users table; collected during registration, no verification required.
- **Database columns added:** `phone` and `email_confirmed_at` added to users table schema.
- **New screens added:** EmailVerificationPendingScreen and SetNewPasswordScreen added to screen inventory.
- **Security rules updated:** bcrypt cost factor 12 (Supabase Auth), rate limiting 10 req/min on backend auth endpoints, HTTPS enforcement, token logging prohibition.
- **Test cases expanded:** Added Supabase client tests, rate limiting tests, email verification E2E, password reset E2E.
- **Environment config updated:** Specific Supabase env vars (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET).
- **Task breakdown updated:** Expanded from 8 to 15 tasks with Supabase-specific implementation tasks.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main system docs.

## 2026-02-07
- Created full Module 1 documentation pack under `docs/modules/MOD-01-authentication-and-identity/`.
- Added governance, catalog, specifications, API contracts, data docs, screen docs, dependencies, testing, implementation, AI execution, and traceability files.
