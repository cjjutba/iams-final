# Users Table Profile Fields

## Table
`users`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-02 |
|---|---|---|---|
| id | UUID | PK | Primary identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Profile and login identity |
| role | VARCHAR(20) | NOT NULL | Authorization behavior |
| first_name | VARCHAR(100) | optional | Profile display/update |
| last_name | VARCHAR(100) | optional | Profile display/update |
| student_id | VARCHAR(50) | UNIQUE | Student profile context |
| is_active | BOOLEAN | DEFAULT true | Account lifecycle state |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Update audit |

## Protected/Restricted Fields
- `role` (admin-controlled)
- `student_id` (restricted update policy)
- `is_active` (admin lifecycle control)
- `password_hash` (never exposed through MOD-02 responses)
