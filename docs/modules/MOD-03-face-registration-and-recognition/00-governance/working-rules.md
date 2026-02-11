# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-03`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-03` and at least one `FUN-03-*` ID.

## Scope Control
- Implement only `FUN-03-01` to `FUN-03-05` under this module.
- Do not add attendance/presence business logic in this module.

## Auth Rules
- Student-facing endpoints (`POST /face/register`, `GET /face/status`) require Supabase JWT verification via middleware from MOD-01.
- Edge-facing endpoint (`POST /face/recognize`) requires shared API key (`X-API-Key` header) — no Supabase JWT.
- Backend must verify `is_active = true` and `email_confirmed_at IS NOT NULL` on JWT-protected routes (from MOD-01).

## Quality Rules
- Registration images must pass validation gates before embedding generation.
- Recognition threshold must be configurable (via `RECOGNITION_THRESHOLD` env var).
- API responses must follow documented envelopes (include optional `message` field).
- FAISS and DB mapping must stay consistent.
- Backend handles resize from edge crop size to model input size (160x160).

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-03 FUN-03-04`
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
