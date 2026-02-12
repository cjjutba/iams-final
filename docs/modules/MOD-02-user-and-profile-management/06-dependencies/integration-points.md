# Integration Points

## Backend Integrations
- Supabase JWT middleware for authentication and role checks (from MOD-01).
- Supabase Admin API for user deletion (`supabase.auth.admin.deleteUser(id)`).
- User repository and DB query layer.
- Validation schemas for patch payloads (allowed/restricted field enforcement).
- Logging/audit for lifecycle operations.

## Mobile Integrations
- Profile screens (`SCR-015`, `SCR-016`, `SCR-027`, `SCR-028`).
- State manager for user profile cache/update.
- API service wrappers for `/users/*` endpoints with Supabase JWT.
- Phone input component for editable phone field.

## Cross-Module Integrations
- `MOD-01`: Supabase JWT middleware, user context, Supabase Admin API client.
- `MOD-03`: Face registration lifecycle — FAISS cleanup on user deletion.
- `MOD-09` and `MOD-10`: Profile UI behavior in student/faculty mobile apps.

## Supabase Auth Integration (Delete)
- On `DELETE /users/{id}`, backend calls `supabase.auth.admin.deleteUser(id)` to remove the Supabase Auth record.
- Uses `SUPABASE_SERVICE_ROLE_KEY` for Admin API access.
- Rollback local changes if Supabase Auth deletion fails.
