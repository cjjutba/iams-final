# Endpoint Contract: DELETE /users/{id}

## Function Mapping
- `FUN-02-04`

## Purpose
Permanently delete user with full cleanup across local DB, Supabase Auth, face registrations, and FAISS index.

## Auth
- Header: `Authorization: Bearer <supabase_jwt>`
- Required role: admin

## Path Parameter
- `id` (UUID)

## Backend Process
1. Verify admin role from Supabase JWT.
2. Verify user exists in local DB.
3. Delete related `face_registrations` records.
4. Coordinate FAISS index cleanup (remove embedding or schedule rebuild).
5. Delete user from Supabase Auth via Admin API (`supabase.auth.admin.deleteUser(id)`).
6. Delete user from local `users` table (CASCADE to any remaining related records).
7. Return success response.

## Rollback
- If Supabase Auth deletion (step 5) fails, roll back local changes (steps 3-4) and return `500`.

## Success Response
```json
{
  "success": true,
  "message": "User permanently deleted"
}
```

## Error Cases
- `401`: missing/invalid Supabase JWT
- `403`: unauthorized caller (non-admin)
- `404`: user not found
- `500`: Supabase Auth deletion failed (local changes rolled back)

## Caller Context
- Admin lifecycle operations and scripts.
