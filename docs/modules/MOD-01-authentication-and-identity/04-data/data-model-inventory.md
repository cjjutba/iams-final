# Data Model Inventory

## Primary Data Stores Used by MOD-01
1. `users` table (Supabase/PostgreSQL)
2. University identity validation dataset (CSV/JRMSU source)
3. Token/session values (JWT access + refresh tokens)

## Entities
- User account identity and credentials
- Registration verification source identity record
- Session credential artifacts

## Ownership
- `users`: backend data layer
- Validation dataset: data import/ops process
- Tokens: auth service and mobile session manager
