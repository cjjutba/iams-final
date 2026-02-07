# MOD-02: User and Profile Management

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Manage user records and profile updates.

Functions:
- `FUN-02-01`: List users (admin scope).
- `FUN-02-02`: Get user by ID.
- `FUN-02-03`: Update user profile fields.
- `FUN-02-04`: Delete/deactivate user.

API Contracts:
- `GET /users?role=student&page=1&limit=20`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`

Data:
- `users`
- `face_registrations` (cascade impact on delete/deactivate)

Screens:
- `SCR-015` StudentProfileScreen
- `SCR-016` StudentEditProfileScreen
- `SCR-027` FacultyProfileScreen
- `SCR-028` FacultyEditProfileScreen

Done Criteria:
- Role-based access enforced.
- Profile edits validated and persisted.
- Delete/deactivate behavior documented and safe.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
