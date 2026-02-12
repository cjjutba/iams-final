# Goal and Objectives

## Module Goal
Provide secure, reliable, and role-aware authentication and identity verification for students and faculty using **Supabase Auth** as the authentication provider, consistent with MVP rules and thesis requirements.

## Primary Objectives
1. Verify student identity against university-provided data before registration.
2. Register student accounts in Supabase Auth + local database only after successful identity verification; trigger email verification.
3. Enforce email verification: users must confirm their email before accessing protected resources.
4. Authenticate student and faculty login via Supabase client SDK with token-based sessions.
5. Provide automatic token refresh via Supabase client and authenticated profile retrieval via backend.
6. Enforce role restrictions (faculty login only in MVP; no faculty self-registration).
7. Provide password reset flow via Supabase client SDK.

## Success Outcomes
- Auth endpoints are stable and meet documented response formats.
- Unauthorized access is consistently blocked (invalid/expired JWT returns 401).
- Inactive users and unverified emails are blocked on protected routes (403).
- Registration flow fails safely when identity verification fails.
- Faculty accounts are controlled through pre-seeding, not open signup.
- Email verification works end-to-end (Supabase sends email, user clicks link, backend enforces).
- Password reset works end-to-end (Supabase sends email, user clicks link, sets new password).

## Non-Goals (for MOD-01 MVP)
- Full admin dashboard implementation.
- Social/OAuth sign-in providers.
- MFA rollout.
- Phone number verification (SMS).
- Complex account recovery beyond email-based password reset.

## Stakeholders
- Students: register and authenticate.
- Faculty: authenticate with pre-seeded accounts.
- Admin/Operations: seed faculty and maintain identity datasets.
- Backend/Mobile implementers: integrate with auth contracts.
