# MVP Scope

## In Scope
- Student identity verification (registration step 1).
- Student account registration after verified identity.
- Student and faculty login.
- Token refresh flow.
- Current user endpoint (`/auth/me`).
- Faculty login-only policy with pre-seeded accounts.

## Out of Scope
- Faculty self-registration.
- Admin UI for user management.
- Advanced auth (MFA, OAuth providers).
- Biometric login on mobile device.

## MVP Constraints
- Uses university-provided student/faculty data (CSV/JRMSU process).
- Mobile app may use Supabase Auth or backend-issued JWT based on selected option.
- Protected routes must validate token and role.

## MVP Gate Criteria
- `FUN-01-01` through `FUN-01-05` implemented and tested.
- Error handling for invalid credentials/token implemented.
- Registration flow blocks unverified students.
- Faculty login works with pre-seeded records only.
