# Business Rules

## Auth Provider
**Supabase Auth** — All MOD-02 endpoints are protected by Supabase JWT verification middleware from MOD-01. User credentials are managed by Supabase Auth; no `password_hash` is stored in the local `users` table.

## Access Rules
1. User listing is admin-only.
2. User retrieval is admin-only unless requester is fetching own record.
3. Profile update is allowed for own profile (first_name, last_name, phone); broader updates (role, student_id, is_active) require admin privileges.
4. User deletion is admin-only.

## Data Rules
1. `email` is immutable after registration — cannot be changed by any role, including admin.
2. `email` remains unique.
3. `student_id` remains unique for student role.
4. `role` changes are restricted to admin flow.
5. `is_active` changes are restricted to admin flow.
6. `phone` is optional, max 20 characters.

## Field Editability Matrix
| Field | Student (Own) | Faculty (Own) | Admin |
|---|---|---|---|
| first_name | Editable | Editable | Editable |
| last_name | Editable | Editable | Editable |
| phone | Editable | Editable | Editable |
| email | Immutable | Immutable | Immutable |
| role | Restricted | Restricted | Editable |
| student_id | Restricted | N/A | Editable |
| is_active | Restricted | Restricted | Editable |

## Delete Rules
1. MVP uses permanent hard delete only (no soft delete / deactivation).
2. Delete must remove user from:
   - Local `users` table (CASCADE to related records).
   - Supabase Auth via Admin API (`supabase.auth.admin.deleteUser(id)`).
   - `face_registrations` table.
   - FAISS index (remove embedding or schedule rebuild).
3. If Supabase Auth deletion fails, the entire operation should roll back.
4. Only admin can perform delete operations.

## Security Rules
1. API responses must not expose Supabase Auth internal metadata.
2. Sensitive profile changes must be audited in logs.
3. Authorization checks happen before DB writes.
4. All endpoints are protected by Supabase JWT middleware — requests without valid JWT are rejected with `401`.
