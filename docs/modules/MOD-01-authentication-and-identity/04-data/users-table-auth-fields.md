# Users Table Auth Fields

## Table
`users`

## Auth-Relevant Columns
| Column | Type | Constraints | Use in MOD-01 |
|---|---|---|---|
| id | UUID | PK | Subject identifier in tokens and API responses; maps to Supabase Auth `sub` claim |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier; must match Supabase Auth user email |
| password_hash | VARCHAR(255) | NOT NULL | Not used directly (Supabase Auth handles password); kept for compatibility |
| role | VARCHAR(20) | NOT NULL | Access and policy behavior (student, faculty, admin) |
| first_name | VARCHAR(100) | optional | Profile payload |
| last_name | VARCHAR(100) | optional | Profile payload |
| student_id | VARCHAR(50) | UNIQUE | Student verification mapping |
| phone | VARCHAR(20) | optional | Contact number; collected during registration; no verification required |
| is_active | BOOLEAN | DEFAULT true | Login gating; backend checks on protected route access |
| email_confirmed_at | TIMESTAMPTZ | nullable | Email verification timestamp; synced from Supabase Auth; backend enforces NOT NULL on protected routes |
| created_at | TIMESTAMPTZ | DEFAULT now() | Audit field |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Audit field |

## Required Indexes
- `idx_users_email`
- `idx_users_student_id`
- `idx_users_role`

## Supabase Auth Sync Notes
- `users.id` must match the Supabase Auth user ID (`sub` claim in JWT).
- `email_confirmed_at` should be synced from Supabase Auth user metadata when the user verifies their email.
- Sync can be done via: (a) Supabase database trigger/webhook, or (b) backend checks Supabase Auth on `GET /auth/me` and updates local record.

## Security Notes
- Never expose `password_hash` in API responses.
- Password management is handled by Supabase Auth; the local `password_hash` field may be unused or used as a fallback.
- `email_confirmed_at` is the source of truth for email verification enforcement.
