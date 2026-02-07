# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-06`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-06` and at least one `FUN-06-*` ID.

## Scope Control
- Implement only `FUN-06-01` to `FUN-06-06` under this module.
- Do not implement presence scoring logic owned by `MOD-07`.

## Quality Rules
- Enforce unique attendance record per student/schedule/date.
- Manual updates must include audit-friendly metadata (`remarks`, actor, timestamp).
- Date filters must be validated and deterministic.
- Live attendance endpoint must reflect active session state.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-06 FUN-06-05`
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
