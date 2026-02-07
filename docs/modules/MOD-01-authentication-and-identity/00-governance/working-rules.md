# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-01`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-01` and at least one `FUN-01-*` ID.

## Scope Control
- Implement only `FUN-01-01` to `FUN-01-05` under this module.
- Do not add unrelated profile CRUD or attendance features in this module.

## Quality Rules
- All protected auth routes require bearer token verification.
- Errors must follow documented JSON error shape.
- Passwords are never stored in plain text.
- Sensitive values are only sourced from env variables.

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
