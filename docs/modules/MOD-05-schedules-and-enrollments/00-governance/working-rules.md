# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-05`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-05` and at least one `FUN-05-*` ID.

## Scope Control
- Implement only `FUN-05-01` to `FUN-05-05` under this module.
- Do not add attendance/presence decision logic in this module.

## Quality Rules
- Schedule time/day filters must be deterministic.
- Enrollment uniqueness constraint must be enforced.
- Role-based access to schedule data must be validated.
- Responses must follow documented API envelope.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-05 FUN-05-03`
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
