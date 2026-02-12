# Test Strategy (MOD-02)

## Scope
Validate profile retrieval/update behavior, role authorization, field restrictions, email immutability, phone handling, and permanent delete with Supabase Auth cleanup.

## Test Types
- Unit tests: user service validation, field authorization, email immutability enforcement.
- Integration tests: `/users/*` endpoints with Supabase JWT, error paths, Supabase Auth deletion.
- E2E checks: profile view/edit on student and faculty flows, admin delete flow.

## Priority Test Areas
1. Authorization behavior (admin vs non-admin) via Supabase JWT.
2. Field-level validation: editable fields (first_name, last_name, phone) and immutable fields (email).
3. Pagination/filter correctness on list endpoint.
4. Permanent delete behavior: local DB + Supabase Auth + face registrations cleanup.
5. Phone field handling in responses and updates.
6. Rollback behavior when Supabase Auth deletion fails.

## Exit Criteria
- All critical user/profile tests pass.
- No blocker/high defects in role, lifecycle, or field restriction logic.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
- Delete operations clean up both local DB and Supabase Auth.
