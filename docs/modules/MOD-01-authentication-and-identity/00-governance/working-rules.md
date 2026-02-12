# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-01`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-01` and at least one `FUN-01-*` ID.

## Scope Control
- Implement only `FUN-01-01` to `FUN-01-07` under this module.
- Do not add unrelated profile CRUD or attendance features in this module.
- Backend implements only: `POST /auth/verify-student-id`, `POST /auth/register`, `GET /auth/me`.
- Mobile implements Supabase client SDK operations for login (`FUN-01-03`), token refresh (`FUN-01-04`), password reset (`FUN-01-06`, `FUN-01-07`).
- Email verification is triggered automatically by Supabase Auth on registration; backend enforces `email_confirmed_at`.

## Quality Rules
- All protected auth routes require Supabase JWT verification.
- Errors must follow documented JSON error shape.
- Passwords are managed by Supabase Auth (bcrypt cost factor 12); never stored or hashed locally.
- Sensitive values are only sourced from env variables (`SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, etc.).
- Backend must verify `is_active = true` and `email_confirmed_at IS NOT NULL` on all protected routes.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-01 FUN-01-03`
- Any API contract change must update:
  - `03-api/api-inventory.md`
  - relevant endpoint file(s)
  - `10-traceability/traceability-matrix.md`

## Change Process
1. Propose doc updates.
2. Review consistency across API/data/screens/testing docs.
3. Implement code.
4. Run tests.
5. Update traceability and changelog.
