# Profile Screen Flows

## Student Profile View Flow
1. Open `SCR-015` StudentProfileScreen.
2. Call `GET /users/{id}` with Supabase JWT for current user context.
3. Render profile fields: name, email, student_id, phone, email_confirmed status, created_at.

## Student Profile Edit Flow
1. Open `SCR-016` StudentEditProfileScreen.
2. Display editable fields: first_name, last_name, phone.
3. Display read-only fields: email (shown but not editable).
4. Submit `PATCH /users/{id}` with Supabase JWT.
5. On success, refresh profile view.
6. On email change attempt, show "Email cannot be changed" error.

## Faculty Profile View/Edit Flows
1. Open `SCR-027` FacultyProfileScreen or `SCR-028` FacultyEditProfileScreen.
2. Use same get/update endpoint pattern as student.
3. Editable fields: first_name, last_name, phone.
4. Read-only fields: email (immutable).
5. Enforce field restrictions and role-aware behavior.

## Admin User Flow (API-Level)
1. List users via `GET /users?role=...` with admin Supabase JWT.
2. Inspect individual user via `GET /users/{id}`.
3. Delete user permanently via `DELETE /users/{id}` when needed.
4. Delete removes user from local DB, Supabase Auth, face registrations, and FAISS.
