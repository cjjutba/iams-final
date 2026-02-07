# Function Specifications

## FUN-02-01 List Users
Goal:
- Return paginated and optionally filtered users list for admin workflows.

Inputs:
- Query params: `role`, `page`, `limit`.

Process:
1. Validate query parameters.
2. Authorize admin access.
3. Query user repository with filters and pagination.
4. Return list plus pagination metadata.

Outputs:
- `200` with `data[]` and `pagination`.

Validation Rules:
- Reject invalid page/limit values with `400`.
- Reject non-admin callers with `403`.

## FUN-02-02 Get User
Goal:
- Return user record by ID with policy-aware access.

Inputs:
- Path param `id`.

Process:
1. Validate UUID format.
2. Authorize requester (admin or own record depending on policy).
3. Fetch user by ID.
4. Return safe response payload.

Outputs:
- `200` with user data.

Validation Rules:
- Return `404` if user not found.
- Return `403` for unauthorized access.

## FUN-02-03 Update User
Goal:
- Update allowed profile fields with proper validation and authorization.

Inputs:
- Path param `id`.
- Payload with allowed profile fields.

Process:
1. Validate request payload and allowed fields.
2. Authorize requester (admin or own record).
3. Apply update and persist.
4. Return updated safe profile response.

Outputs:
- `200` with updated user data.

Validation Rules:
- Reject restricted fields (for example role changes by non-admin).
- Reject invalid formats and uniqueness violations.

## FUN-02-04 Delete/Deactivate User
Goal:
- Remove or deactivate user safely, without breaking related modules.

Inputs:
- Path param `id`.

Process:
1. Authorize admin action.
2. Resolve safe strategy (soft delete preferred in MVP).
3. Handle related records (for example face registrations).
4. Return operation result.

Outputs:
- `200` with operation confirmation.

Validation Rules:
- Return `404` if user not found.
- Return `403` if caller lacks privileges.
- Document whether operation is soft delete or hard delete.
