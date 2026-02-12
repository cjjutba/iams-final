# Face Registration Lifecycle Impact

## Related Table
`face_registrations`

## Delete Policy (MVP)
MVP uses **permanent hard delete** only. No soft delete / deactivation.

## Impact on Delete (FUN-02-04)
When a user is permanently deleted via `DELETE /users/{id}`:

1. **Face registrations deleted** — All `face_registrations` rows linked to the user are deleted.
2. **FAISS index cleanup** — The corresponding embedding is removed from the FAISS index, or the index is scheduled for rebuild. (FAISS `IndexFlatIP` does not support native delete; use rebuild or side-structure filtering.)
3. **Supabase Auth user deleted** — The Supabase Auth record is deleted via Admin API (`supabase.auth.admin.deleteUser(id)`).
4. **Local user row deleted** — The `users` row is deleted (CASCADE to any remaining related records).

## Deletion Order
1. Delete `face_registrations` rows.
2. Coordinate FAISS cleanup.
3. Delete Supabase Auth user.
4. Delete local `users` row.
5. If step 3 fails, roll back steps 1-2 and return error.

## Cross-Module Coordination
- `MOD-02` (lifecycle action) triggers deletion.
- `MOD-03` (face registry/index) must handle FAISS cleanup when notified by MOD-02 delete service.
- `MOD-01` (Supabase Auth) — user is removed from Supabase Auth via Admin API.
