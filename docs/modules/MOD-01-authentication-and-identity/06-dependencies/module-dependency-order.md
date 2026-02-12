# Module Dependency Order

## Upstream Dependencies for MOD-01
1. `MOD-11` Data Import and Seed Operations
- Required for identity dataset availability and faculty pre-seeding.
2. Supabase project setup
- Required for Supabase Auth, PostgreSQL, JWT secret, email templates.

## MOD-01 Before/After Sequence
1. Set up Supabase project (Auth + PostgreSQL + email templates).
2. Implement `MOD-11` baseline data readiness (student CSV import, faculty pre-seeding).
3. Implement `MOD-01` auth and identity endpoints + Supabase client integration.
4. Then implement dependent modules:
- `MOD-02` User/Profile management
- `MOD-09` Student mobile app
- `MOD-10` Faculty mobile app

## Internal Function Dependency Order
1. `FUN-01-01` Verify student identity (backend endpoint)
2. `FUN-01-02` Register student account (backend endpoint + Supabase Admin API)
3. Email verification (Supabase automatic; user clicks link)
4. `FUN-01-03` Login (Supabase client SDK)
5. `FUN-01-04` Refresh token (Supabase client SDK; automatic)
6. `FUN-01-05` Get current user (backend endpoint; JWT-protected)
7. `FUN-01-06` Request password reset (Supabase client SDK)
8. `FUN-01-07` Complete password reset (Supabase client SDK)

## Rationale
- Identity check and account creation establish user records in both Supabase Auth and local DB.
- Email verification must happen before login can succeed (backend enforces).
- Token lifecycle (Supabase JWT) is needed before protected route retrieval (`GET /auth/me`).
- Password reset is independent but requires an existing account.
