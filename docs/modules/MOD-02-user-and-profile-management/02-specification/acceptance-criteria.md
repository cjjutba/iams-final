# Acceptance Criteria

## Function-Level Acceptance

### FUN-02-01 List Users
- Given admin token and valid query params, endpoint returns paginated users list with `200`.
- Given non-admin token, endpoint returns `403`.
- Given invalid page/limit params, endpoint returns `400`.
- Response includes phone and email_confirmed fields for each user.

### FUN-02-02 Get User
- Given valid user ID and authorized caller (admin or own record), endpoint returns user profile with `200`.
- Response includes: id, email, first_name, last_name, role, student_id, phone, is_active, email_confirmed, created_at.
- Given unknown ID, endpoint returns `404`.
- Given unauthorized caller (non-admin requesting another user), endpoint returns `403`.

### FUN-02-03 Update User
- Given valid payload (first_name, last_name, phone) and authorized caller, endpoint updates and returns profile data with `200`.
- Given attempt to change email, endpoint returns `400` (immutable field) regardless of role.
- Given restricted fields (role, student_id, is_active) by non-admin, endpoint returns `403`.
- Given restricted fields (role, student_id, is_active) by admin, endpoint updates successfully with `200`.
- Given invalid field format, endpoint returns `400`.
- Given unauthorized caller, endpoint returns `403`.

### FUN-02-04 Delete User
- Given authorized admin and existing user, endpoint permanently deletes user from local DB and Supabase Auth with `200`.
- Face registrations and FAISS index are cleaned up on delete.
- Given unknown ID, endpoint returns `404`.
- Given non-admin caller, endpoint returns `403`.
- If Supabase Auth deletion fails, local changes are rolled back and endpoint returns `500`.

## Module-Level Acceptance
- Profile endpoints and screens remain consistent.
- Role-based controls are enforced across all user endpoints via Supabase JWT.
- Delete behavior permanently removes user from both local DB and Supabase Auth.
- Email is immutable across all update paths.
- Phone field is returned in profile responses and editable via PATCH.
