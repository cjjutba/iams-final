# MOD-09: Student Mobile App

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Provide student onboarding, registration, and attendance visibility.

Functions:
- `FUN-09-01`: Onboarding and welcome flow.
- `FUN-09-02`: Student login and token persistence.
- `FUN-09-03`: 4-step student registration flow.
- `FUN-09-04`: Attendance dashboard and history.
- `FUN-09-05`: Profile and face re-registration.
- `FUN-09-06`: Student notifications.

Screens:
- Shared: `SCR-001`, `SCR-002`, `SCR-003`
- Auth and registration: `SCR-004`, `SCR-006`, `SCR-007`, `SCR-008`, `SCR-009`, `SCR-010`
- Student portal: `SCR-011`, `SCR-012`, `SCR-013`, `SCR-014`, `SCR-015`, `SCR-016`, `SCR-017`, `SCR-018`

Done Criteria:
- Registration flow blocks progression on invalid data.
- All student API calls use authenticated session.
- Empty, loading, and error states are implemented.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
