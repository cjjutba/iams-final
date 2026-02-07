# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-03`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-03` and at least one `FUN-03-*` ID.

## Scope Control
- Implement only `FUN-03-01` to `FUN-03-05` under this module.
- Do not add attendance/presence business logic in this module.

## Quality Rules
- Registration images must pass validation gates before embedding generation.
- Recognition threshold must be configurable.
- API responses must follow documented envelopes.
- FAISS and DB mapping must stay consistent.

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
