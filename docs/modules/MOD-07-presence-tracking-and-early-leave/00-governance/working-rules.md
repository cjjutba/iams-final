# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-07`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-07` and at least one `FUN-07-*` ID.

## Scope Control
- Implement only `FUN-07-01` to `FUN-07-06` under this module.
- Do not implement websocket transport details (owned by `MOD-08`).

## Quality Rules
- Scan interval and threshold values must be configurable.
- Miss-counter resets and increments must be deterministic.
- Early-leave flags require threshold condition fulfillment.
- Presence logs should support accurate audit/replay.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-07 FUN-07-04`
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
