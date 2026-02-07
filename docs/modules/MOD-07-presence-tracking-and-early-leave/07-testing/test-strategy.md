# Test Strategy (MOD-07)

## Scope
Validate session state management, scan loop behavior, miss counter transitions, early-leave flagging, and presence score calculations.

## Test Types
- Unit tests: state transitions, threshold logic, score formula.
- Integration tests: `/presence/*` endpoint responses and filters.
- Scenario tests: continuous presence, early leave, recovery after brief absence.

## Priority Test Areas
1. Miss counter increment/reset correctness.
2. Early-leave threshold trigger behavior.
3. Recovery scenario (brief absence) behavior.
4. Presence log and early-leave query accuracy.

## Exit Criteria
- All critical presence tests pass.
- No blocker/high defects in state/threshold behavior.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
