# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-02`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-02` and at least one `FUN-02-*` ID.

## Scope Control
- Implement only `FUN-02-01` to `FUN-02-04` under this module.
- Do not add auth token flows, attendance logic, or schedule business rules in this module.

## Quality Rules
- Role-based access must be enforced consistently.
- Profile updates must validate allowed fields and data types.
- Delete/deactivate actions must preserve referential integrity.
- Responses must follow documented success/error shape.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-02 FUN-02-03`
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
