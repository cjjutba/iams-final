# Data Model Inventory

## Primary Data Stores Used by MOD-02
1. `users` table (profile and identity fields; no password_hash)
2. `face_registrations` table (lifecycle linkage — cascade delete on user removal)
3. Supabase Auth user records (credentials and email verification; deleted via Admin API on user removal)

## Entities
- User profile record (local `users` table)
- User role and account state (`is_active`)
- Phone number (optional contact field)
- Email confirmation status (`email_confirmed_at`, synced from Supabase Auth)
- Face registration linkage for lifecycle handling
- Supabase Auth user record (external; coordinated on delete)

## Ownership
- `users`: backend data layer (local PostgreSQL)
- `face_registrations`: face module data, referenced for lifecycle impact
- Supabase Auth `auth.users`: Supabase Auth service (external)

## Supabase Auth Sync
- `users.id` matches Supabase Auth user ID (UUID).
- `users.email_confirmed_at` is synced from Supabase Auth.
- On user deletion (FUN-02-04), both local `users` row and Supabase Auth user are permanently deleted.
