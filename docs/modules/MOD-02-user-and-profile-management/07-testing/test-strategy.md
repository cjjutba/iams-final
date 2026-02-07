# Test Strategy (MOD-02)

## Scope
Validate profile retrieval/update behavior, role authorization, and user lifecycle operations.

## Test Types
- Unit tests: user service validation and authorization checks.
- Integration tests: `/users/*` endpoints and error paths.
- E2E checks: profile view/edit on student and faculty flows.

## Priority Test Areas
1. Authorization behavior (admin vs non-admin).
2. Field-level validation and update restrictions.
3. Pagination/filter correctness on list endpoint.
4. Safe delete/deactivate behavior with linked records.

## Exit Criteria
- All critical user/profile tests pass.
- No blocker/high defects in role or lifecycle logic.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
