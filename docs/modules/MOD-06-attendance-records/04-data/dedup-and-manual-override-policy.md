# Dedup and Manual Override Policy

## Dedup Policy
1. One attendance row per `(student_id, schedule_id, date)` — enforced by UNIQUE constraint at database level.
2. Recognition updates (FUN-06-01) upsert existing row, not insert duplicates.
3. If row exists for the same student/schedule/date, update fields (e.g., last seen time) rather than creating a new row.

## Manual Override Policy
1. Faculty or admin role required (Supabase JWT with faculty/admin role). Student role returns 403.
2. Manual entry (FUN-06-05) can create a missing row or update an existing status.
3. `remarks` is required for all manual entries (audit trail compliance). Returns 422 if missing.
4. `updated_by` is automatically set to the JWT `sub` (user ID of faculty/admin performing the override).
5. `updated_at` timestamp is automatically updated on every manual override.
6. Status must be one of: `present`, `late`, `absent`, `early_leave`. Returns 422 for invalid values.

## Conflict Handling
- Uniqueness constraint prevents concurrent duplicate inserts.
- Manual overrides use upsert strategy on `(student_id, schedule_id, date)`.
- If simultaneous system update and manual override occur, the manual override takes precedence (last write wins with audit trail).

## Audit Trail
All manual overrides are auditable via:
- `remarks`: text explaining the reason for the override.
- `updated_by`: UUID of the faculty/admin who performed the override (FK → users.id).
- `updated_at`: timestamp of when the override was performed.
