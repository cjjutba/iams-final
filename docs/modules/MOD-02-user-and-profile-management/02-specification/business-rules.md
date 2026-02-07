# Business Rules

## Access Rules
1. User listing is admin-only.
2. User retrieval is admin-only unless requester is fetching own record.
3. Profile update is allowed for own profile; broader updates require admin privileges.
4. User delete/deactivate is admin-only.

## Data Rules
1. `email` remains unique.
2. `student_id` remains unique for student role.
3. `role` changes are restricted to admin flow.
4. `is_active=false` blocks future authentication.

## Delete/Deactivate Rules
1. MVP default should prefer deactivate over hard delete.
2. If hard delete is used, cascade impact must be documented and tested.
3. Face registration records must be handled consistently with user status.

## Security Rules
1. API responses must not expose `password_hash`.
2. Sensitive profile changes must be audited in logs.
3. Authorization checks happen before DB writes.
