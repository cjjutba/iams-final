# Integration Points

## Backend Integrations
- Auth dependency middleware for role checks.
- User repository and DB query layer.
- Validation schemas for patch payloads.
- Logging/audit for lifecycle operations.

## Mobile Integrations
- Profile screens (`SCR-015`, `SCR-016`, `SCR-027`, `SCR-028`).
- State manager for user profile cache/update.
- API service wrappers for `/users/*` endpoints.

## Cross-Module Integrations
- `MOD-01`: token and user context.
- `MOD-03`: face registration lifecycle linkage.
- `MOD-09` and `MOD-10`: profile UI behavior.
