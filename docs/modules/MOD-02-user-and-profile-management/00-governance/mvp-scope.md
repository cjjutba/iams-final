# MVP Scope

## In Scope
- Admin user listing with filters and pagination.
- User retrieval by ID.
- Student/faculty profile updates through controlled fields.
- Safe delete/deactivate user behavior.
- Role-based policy enforcement for all `/users/*` endpoints.

## Out of Scope
- Admin dashboard UI.
- Bulk user import UI.
- Advanced role permission management UI.
- Self-service account deletion workflow design beyond API behavior.

## MVP Constraints
- User data is stored in Supabase/PostgreSQL `users` table.
- Delete/deactivate operations must account for related data (for example `face_registrations`).
- Faculty accounts are pre-seeded in MVP and should not be altered by unprivileged users.

## MVP Gate Criteria
- `FUN-02-01` through `FUN-02-04` implemented and tested.
- Unauthorized role access is blocked.
- Allowed profile fields update correctly.
- Delete/deactivate behavior is clearly defined and validated.
