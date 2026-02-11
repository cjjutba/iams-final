# Changelog (MOD-02 Docs)

## 2026-02-12
- **Supabase Auth alignment:** All endpoints now explicitly reference Supabase JWT authentication (aligned with MOD-01 decisions).
- **password_hash removed:** Removed `password_hash` from users table and all references; passwords are managed by Supabase Auth.
- **Phone field added:** Added `phone VARCHAR(20)` (optional) to profile fields, API responses, edit forms, and test cases.
- **email_confirmed_at added:** Added `email_confirmed_at` to profile fields as read-only (synced from Supabase Auth).
- **created_at added:** Added `created_at` to profile response fields.
- **Email immutability:** Email is now explicitly immutable — cannot be changed by any role (including admin). PATCH returns `400` on email change attempt.
- **Field editability matrix:** Added explicit field rules for PATCH — students/faculty can edit first_name, last_name, phone; admin can additionally edit role, student_id, is_active.
- **Delete = permanent hard delete:** Changed from soft delete preference to permanent hard delete. Delete now removes user from local DB, Supabase Auth (via Admin API), face registrations, and FAISS index. Rollback on Supabase Auth failure.
- **API responses expanded:** GET /users/{id} and GET /users now return full profile fields (phone, student_id, is_active, email_confirmed, created_at).
- **Canonical sources fixed:** Replaced stale references (master-blueprint.md, testing.md) with correct files (architecture.md, implementation.md).
- **Environment config updated:** Added specific Supabase variables (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, DATABASE_URL).
- **Test cases expanded:** Added phone tests, email immutability tests, Supabase Auth deletion tests, rollback tests. Expanded from 4 unit + 8 integration + 4 E2E to 7 unit + 12 integration + 6 E2E.
- **Task breakdown updated:** Expanded from 7 to 9 tasks with Supabase Auth deletion and rollback tasks.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs and MOD-01.

## 2026-02-07
- Created full Module 2 documentation pack under `docs/modules/MOD-02-user-and-profile-management/`.
- Added governance, catalog, specifications, API contracts, data docs, screen docs, dependencies, testing, implementation, AI execution, and traceability files.
