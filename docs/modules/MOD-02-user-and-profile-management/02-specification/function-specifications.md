# Function Specifications

## FUN-02-01 List Users
Goal:
- Return paginated and optionally filtered users list for admin workflows.

Inputs:
- Query params: `role`, `page`, `limit`.

Process:
1. Validate query parameters.
2. Verify Supabase JWT; authorize admin access.
3. Query user repository with filters and pagination.
4. Return list plus pagination metadata.

Outputs:
- `200` with `data[]` and `pagination`.

Validation Rules:
- Reject invalid page/limit values with `400`.
- Reject non-admin callers with `403`.

Implementation:
- Backend endpoint: `GET /users`
- Auth: Supabase JWT middleware + admin role check.

## FUN-02-02 Get User
Goal:
- Return user record by ID with policy-aware access.

Inputs:
- Path param `id`.

Process:
1. Validate UUID format.
2. Verify Supabase JWT; authorize requester (admin or own record).
3. Fetch user by ID from local DB.
4. Return safe response payload (including phone, student_id, email_confirmed status).

Outputs:
- `200` with user data.

Response Fields:
- `id`, `email`, `first_name`, `last_name`, `role`, `student_id`, `phone`, `is_active`, `email_confirmed`, `created_at`.

Validation Rules:
- Return `404` if user not found.
- Return `403` for unauthorized access (non-admin requesting another user's record).

Implementation:
- Backend endpoint: `GET /users/{id}`
- Auth: Supabase JWT middleware + ownership or admin check.

## FUN-02-03 Update User
Goal:
- Update allowed profile fields with proper validation and authorization.

Inputs:
- Path param `id`.
- Payload with allowed profile fields.

Allowed Fields (Student/Faculty — Own Profile):
| Field | Type | Rules |
|---|---|---|
| first_name | string | Optional, max 100 chars |
| last_name | string | Optional, max 100 chars |
| phone | string | Optional, max 20 chars |

Restricted Fields (Rejected for Non-Admin):
| Field | Rule |
|---|---|
| email | Immutable — always rejected, even for admin |
| role | Admin-only |
| student_id | Admin-only |
| is_active | Admin-only |

Process:
1. Validate request payload against allowed fields.
2. Reject any attempt to change `email` (immutable for all roles).
3. Verify Supabase JWT; authorize requester (admin or own record).
4. For non-admin: reject restricted fields (role, student_id, is_active).
5. Apply update and persist to local DB.
6. Return updated safe profile response.

Outputs:
- `200` with updated user data.

Validation Rules:
- Reject restricted fields for non-admin with `403`.
- Reject email change attempt with `400` (immutable field).
- Reject invalid formats with `400`.

Implementation:
- Backend endpoint: `PATCH /users/{id}`
- Auth: Supabase JWT middleware + ownership or admin check.

## FUN-02-04 Delete User
Goal:
- Permanently remove user from the system, including Supabase Auth.

Inputs:
- Path param `id`.

Process:
1. Verify Supabase JWT; authorize admin action.
2. Verify user exists in local DB.
3. Delete related `face_registrations` records.
4. Coordinate FAISS index cleanup (remove embedding or mark for rebuild).
5. Delete user from Supabase Auth via Admin API (`supabase.auth.admin.deleteUser(id)`).
6. Delete user from local `users` table.
7. Return operation result.

Outputs:
- `200` with operation confirmation.

Validation Rules:
- Return `404` if user not found.
- Return `403` if caller is not admin.
- If Supabase Auth deletion fails, roll back local changes and return `500`.

Implementation:
- Backend endpoint: `DELETE /users/{id}`
- Auth: Supabase JWT middleware + admin role check.
- Supabase Admin API: `supabase.auth.admin.deleteUser(id)`.
