# Users Table Auth Fields

## Table
`users`

## Auth-Relevant Columns
| Column | Type | Constraints | Use in MOD-01 |
|---|---|---|---|
| id | UUID | PK | Subject identifier in tokens and API responses |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier |
| password_hash | VARCHAR(255) | NOT NULL | Password verification |
| role | VARCHAR(20) | NOT NULL | Access and policy behavior |
| first_name | VARCHAR(100) | optional | Profile payload |
| last_name | VARCHAR(100) | optional | Profile payload |
| student_id | VARCHAR(50) | UNIQUE | Student verification mapping |
| is_active | BOOLEAN | DEFAULT true | Login gating |
| created_at | TIMESTAMPTZ | DEFAULT now() | audit field |
| updated_at | TIMESTAMPTZ | DEFAULT now() | audit field |

## Required Indexes
- `idx_users_email`
- `idx_users_student_id`
- `idx_users_role`

## Security Notes
- Never expose `password_hash` in API responses.
- Password update/reset flows must re-hash before persistence.
