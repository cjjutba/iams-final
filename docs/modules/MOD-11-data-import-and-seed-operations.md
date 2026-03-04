# MOD-11: Data Import and Seed Operations

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Prepare baseline university data needed for MVP operation.

Functions:
- `FUN-11-01`: Import students CSV for identity validation.
- `FUN-11-02`: Seed faculty accounts.
- `FUN-11-03`: Import schedules.
- `FUN-11-04`: Import or map enrollments.

Data:
- `users`
- `schedules`
- `enrollments`
- External CSV datasets

Screens:
- None (operational scripts/module)

Done Criteria:
- Import scripts are repeatable and idempotent.
- Validation reports are generated for bad rows.
- Seeded faculty login is verified.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
