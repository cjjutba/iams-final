# Face Registrations Fields

## Table
`face_registrations`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-03 |
|---|---|---|---|
| id | UUID | PK | registration row id |
| user_id | UUID | FK to users, UNIQUE | one active registration per user |
| embedding_id | VARCHAR(255) | NOT NULL | vector id mapping |
| registered_at | TIMESTAMPTZ | DEFAULT now() | registration timestamp |
| is_active | BOOLEAN | DEFAULT true | lifecycle state |

## Indexes
- `idx_face_user`

## Rules
- Enforce unique active mapping per user.
- Preserve mapping consistency with FAISS writes.
