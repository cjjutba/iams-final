# Module Specification

## Module ID
`MOD-02`

## Purpose
Manage user records and profile updates.

## Core Functions
- `FUN-02-01`: List users (admin scope).
- `FUN-02-02`: Get user by ID.
- `FUN-02-03`: Update user profile fields.
- `FUN-02-04`: Delete/deactivate user.

## API Contracts
- `GET /users?role=student&page=1&limit=20`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`

## Data Dependencies
- `users`
- `face_registrations` (cascade impact on delete/deactivate)

## Screen Dependencies
- `SCR-015` StudentProfileScreen
- `SCR-016` StudentEditProfileScreen
- `SCR-027` FacultyProfileScreen
- `SCR-028` FacultyEditProfileScreen

## Done Criteria
- Role-based access enforced.
- Profile edits validated and persisted.
- Delete/deactivate behavior documented and safe.
