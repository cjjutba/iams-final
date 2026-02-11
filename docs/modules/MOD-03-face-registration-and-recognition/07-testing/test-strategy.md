# Test Strategy (MOD-03)

## Scope
Validate face input quality checks, embedding generation, recognition behavior, FAISS/DB consistency, auth enforcement (Supabase JWT + API key), and MOD-02 deletion coordination.

## Test Types
- Unit tests: image validation, embedding generation, threshold matching, sync logic, API key validation.
- Integration tests: `/face/register`, `/face/recognize`, `/face/status` endpoints with auth scenarios.
- E2E checks: student step-3 registration, re-registration flow, edge recognition with API key.

## Priority Test Areas
1. Image validation failure handling.
2. Embedding output dimensions and stability.
3. Recognize matched vs unmatched behavior.
4. FAISS + DB synchronization through lifecycle operations.
5. Supabase JWT enforcement on register and status endpoints.
6. API key enforcement on recognize endpoint.
7. MOD-02 user deletion triggering face data cleanup.
8. Backend image resize to 160x160 before inference.

## Exit Criteria
- All critical face module tests pass.
- No blocker/high defects in registration/recognition logic.
- Auth scenarios verified (valid JWT, expired JWT, no JWT, valid API key, invalid API key).
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
