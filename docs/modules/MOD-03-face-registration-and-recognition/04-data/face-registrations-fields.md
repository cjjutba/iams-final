# Face Registrations Fields

## Table
`face_registrations`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-03 |
|---|---|---|---|
| id | UUID | PK | registration row id |
| user_id | UUID | FK to users, UNIQUE | one active registration per user |
| embedding_id | VARCHAR(255) | NOT NULL | vector id mapping to FAISS index |
| registered_at | TIMESTAMPTZ | DEFAULT now() | registration timestamp |
| is_active | BOOLEAN | DEFAULT true | lifecycle state |

## Indexes
- `idx_face_user` on (user_id)

## Rules
- Enforce unique active mapping per user.
- Preserve mapping consistency with FAISS writes.
- On re-registration: deactivate old row, create new row, update FAISS.
- On user deletion (MOD-02 trigger): delete row, remove FAISS entry, persist index.

## Note on User Identity
- `user_id` references `users.id` which matches Supabase Auth user ID (from MOD-01).
- No local password storage — Supabase Auth manages credentials.
