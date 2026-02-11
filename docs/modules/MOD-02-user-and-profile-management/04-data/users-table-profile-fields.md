# Users Table Profile Fields

## Table
`users`

## Note on Credentials
Passwords are managed by **Supabase Auth**. There is no `password_hash` column in the local `users` table. The user `id` (UUID) matches the Supabase Auth user ID.

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-02 |
|---|---|---|---|
| id | UUID | PK | Primary identifier (matches Supabase Auth user ID) |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Profile display; immutable after registration |
| role | VARCHAR(20) | NOT NULL | Authorization behavior |
| first_name | VARCHAR(100) | optional | Profile display/update (editable) |
| last_name | VARCHAR(100) | optional | Profile display/update (editable) |
| student_id | VARCHAR(50) | UNIQUE | Student profile context (admin-editable only) |
| phone | VARCHAR(20) | optional | Contact number (editable by user) |
| is_active | BOOLEAN | DEFAULT true | Account lifecycle state (admin-only) |
| email_confirmed_at | TIMESTAMPTZ | nullable | Email verification timestamp (synced from Supabase Auth; read-only) |
| created_at | TIMESTAMPTZ | DEFAULT now() | Account creation audit |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Update audit |

## Field Editability (via PATCH /users/{id})
| Field | Student/Faculty (Own) | Admin |
|---|---|---|
| first_name | Editable | Editable |
| last_name | Editable | Editable |
| phone | Editable | Editable |
| email | Immutable | Immutable |
| role | Restricted | Editable |
| student_id | Restricted | Editable |
| is_active | Restricted | Editable |
| email_confirmed_at | Read-only | Read-only |
| created_at | Read-only | Read-only |

## Protected/Restricted Fields
- `email` (immutable — cannot be changed by any role)
- `role` (admin-controlled)
- `student_id` (admin-controlled)
- `is_active` (admin lifecycle control)
- `email_confirmed_at` (read-only; synced from Supabase Auth)
- `created_at` (read-only; system-generated)
