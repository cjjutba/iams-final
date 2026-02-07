# Test Strategy (MOD-06)

## Scope
Validate attendance mark/upsert behavior, history queries, manual overrides, and live class data outputs.

## Test Types
- Unit tests: dedup/upsert logic, status transitions, summary calculation.
- Integration tests: attendance endpoints and role restrictions.
- E2E checks: student/faculty attendance screens and manual entry flow.

## Priority Test Areas
1. Duplicate-prevention rule.
2. Date-filtered history correctness.
3. Manual entry permissions and audit fields.
4. Live attendance payload consistency.

## Exit Criteria
- All critical attendance tests pass.
- No blocker/high defects in status/update logic.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
