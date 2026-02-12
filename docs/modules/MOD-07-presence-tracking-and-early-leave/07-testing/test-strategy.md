# Test Strategy (MOD-07)

## Scope
Validate session state management, scan loop behavior, miss counter transitions, early-leave flagging, presence score calculations, auth enforcement, and timezone handling.

## Test Types
- **Unit tests:** State transitions, threshold logic, score formula, counter determinism.
- **Integration tests:** `/presence/*` endpoint responses, filters, auth enforcement (401/403).
- **Scenario tests:** Continuous presence, early leave, recovery after brief absence, config changes.

## Priority Test Areas
1. Miss counter increment/reset correctness.
2. Early-leave threshold trigger behavior.
3. Recovery scenario (brief absence) behavior.
4. Presence log and early-leave query accuracy.
5. Auth enforcement: missing JWT (401), wrong role (403), expired JWT (401).
6. Timezone handling: session boundaries use configured `TIMEZONE`.
7. Response envelope format: `success`, `data`, `message` fields present.
8. Dedup: no duplicate early-leave events for same attendance context.
9. Cascade: presence data removed when parent attendance record is deleted.

## Exit Criteria
- All critical presence tests pass.
- No blocker/high defects in state/threshold behavior.
- Auth tests confirm 401 for missing/invalid JWT and 403 for insufficient role.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
