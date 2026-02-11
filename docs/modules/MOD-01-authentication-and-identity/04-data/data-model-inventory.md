# Data Model Inventory

## Primary Data Stores Used by MOD-01
1. `users` table (Supabase PostgreSQL) — user profiles, roles, status, email_confirmed_at
2. Supabase Auth user records — authentication credentials, email verification, password management
3. University identity validation dataset (CSV/JRMSU source) — student identity verification
4. Token/session values — Supabase-issued JWT access + refresh tokens (managed by Supabase client)

## Entities
- User account identity and credentials (Supabase Auth + local `users` table)
- Registration verification source identity record (university dataset)
- Session credential artifacts (Supabase JWT tokens)

## Ownership
- `users` table: backend data layer (local PostgreSQL via Supabase)
- Supabase Auth users: Supabase Auth service (backend creates via Admin API)
- Validation dataset: data import/ops process (`MOD-11`)
- Tokens: Supabase Auth service and mobile Supabase client

## Supabase Auth ↔ Local DB Sync
- On registration: backend creates Supabase Auth user AND local `users` row (same UUID).
- On email verification: Supabase updates its user record; backend syncs `email_confirmed_at` to local `users` table.
- On password reset: Supabase handles entirely; no local DB change needed.
