# Test Strategy (MOD-05)

## Scope
Validate schedule query accuracy, enrollment integrity, role-aware views, and creation validation rules.

## Test Types
- Unit tests: schedule validation, filter logic, role-based query resolution.
- Integration tests: `/schedules/*` endpoint behavior.
- E2E checks: student/faculty schedule screens and roster access.

## Priority Test Areas
1. Day/time filter correctness.
2. `GET /schedules/me` role-specific behavior.
3. Enrollment roster consistency.
4. Create schedule validation and authorization.

## Exit Criteria
- All critical schedule module tests pass.
- No blocker/high defects in role/access or data mapping logic.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
