# MVP Scope

## In Scope
- Admin user listing with filters and pagination.
- User retrieval by ID (admin or own record).
- Student/faculty profile updates through controlled fields (first_name, last_name, phone).
- Email field is immutable after registration.
- Permanent user deletion (hard delete) with full cleanup:
  - Delete from local `users` table.
  - Delete from Supabase Auth via Admin API (`supabase.auth.admin.deleteUser()`).
  - Cascade delete related `face_registrations` and FAISS index cleanup.
- Role-based policy enforcement for all `/users/*` endpoints.

## Out of Scope
- Admin dashboard UI.
- Bulk user import UI.
- Advanced role permission management UI.
- Self-service account deletion workflow design beyond API behavior.
- Rate limiting on user endpoints.
- Soft delete / deactivation (MVP uses hard delete only).

## MVP Constraints
- User data is stored in Supabase/PostgreSQL `users` table.
- User credentials are managed by Supabase Auth (no local `password_hash`).
- All endpoints are protected by Supabase JWT middleware (from MOD-01).
- Delete operations must clean up Supabase Auth user, face registrations, and FAISS index.
- Faculty accounts are pre-seeded in MVP and should not be altered by unprivileged users.

## MVP Gate Criteria
- `FUN-02-01` through `FUN-02-04` implemented and tested.
- Unauthorized role access is blocked.
- Allowed profile fields (first_name, last_name, phone) update correctly.
- Email cannot be changed via PATCH endpoint.
- Delete permanently removes user from local DB and Supabase Auth.
- Related records (face_registrations) are cleaned up on delete.
