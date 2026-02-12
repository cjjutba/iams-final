# Module Specification

## Module ID
`MOD-02`

## Purpose
Manage user records and profile updates, with Supabase Auth lifecycle coordination on delete.

## Auth Context
All endpoints are protected by **Supabase JWT** verification middleware from MOD-01. Credentials are managed by Supabase Auth (no local `password_hash`).

## Core Functions
- `FUN-02-01`: List users (admin scope).
- `FUN-02-02`: Get user by ID (admin or own record).
- `FUN-02-03`: Update user profile fields (first_name, last_name, phone; email immutable).
- `FUN-02-04`: Delete user permanently (local DB + Supabase Auth + face registrations + FAISS).

## API Contracts
- `GET /users?role=student&page=1&limit=20`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`

## Data Dependencies
- `users` (profile fields; no password_hash — managed by Supabase Auth)
- `face_registrations` (cascade delete on user removal)
- Supabase Auth user record (deleted via Admin API on user removal)

## Screen Dependencies
- `SCR-015` StudentProfileScreen
- `SCR-016` StudentEditProfileScreen
- `SCR-027` FacultyProfileScreen
- `SCR-028` FacultyEditProfileScreen

## Done Criteria
- Role-based access enforced via Supabase JWT.
- Profile edits validated and persisted (first_name, last_name, phone).
- Email is immutable via PATCH.
- Delete permanently removes user from local DB, Supabase Auth, face registrations, and FAISS index.
