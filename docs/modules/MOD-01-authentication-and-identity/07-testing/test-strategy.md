# Test Strategy (MOD-01)

## Scope
Validate correctness, security behavior, and error handling for all `FUN-01-*` functions across backend endpoints and Supabase client operations.

## Test Types
- **Unit tests:** JWT verification, Supabase Admin API user creation, identity validation logic, auth service logic.
- **Integration tests:** `/auth/*` backend endpoints with valid/invalid scenarios; Supabase Auth operations.
- **E2E checks:** Registration + email verification + login + session restore via mobile flow.

## Priority Test Areas
1. Credential validation and failure modes (Supabase client errors).
2. Supabase JWT verification on backend (signature, expiry, claims).
3. Identity verification gating registration.
4. Faculty login-only enforcement in MVP.
5. Email verification enforcement on protected routes.
6. Password reset flow end-to-end.
7. Rate limiting on backend auth endpoints (10 req/min).

## Security & Rate Limiting Tests
1. Verify rate limiting on `POST /auth/verify-student-id` (10 req/min).
2. Verify rate limiting on `POST /auth/register` (10 req/min).
3. Ensure proper `429 Too Many Requests` response on rate limit breach.
4. Verify JWT signature validation rejects tampered tokens.
5. Verify expired JWT returns `401`.
6. Verify inactive user returns `403` on `GET /auth/me`.
7. Verify unverified email returns `403` on `GET /auth/me`.

## Exit Criteria
- All critical auth tests pass.
- No blocker/high auth defects remain.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
- Email verification flow works end-to-end.
- Password reset flow works end-to-end.
