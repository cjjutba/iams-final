# Test Strategy (MOD-04)

## Scope
Validate edge capture pipeline reliability, payload correctness, queue policy, and retry recovery behavior.

## Test Types
- Unit tests: queue policy, payload builder, retry decision logic.
- Integration tests: `/face/process` contract and failure handling.
- Scenario tests: server-down queue/recovery behavior.

## Priority Test Areas
1. Payload schema correctness.
2. Queue max-size/TTL behavior.
3. Non-blocking retry while capture continues.
4. Recovery after backend restart.

## Exit Criteria
- All critical edge tests pass.
- No blocker/high defects in queue/retry logic.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
