# Test Strategy (MOD-04)

## Scope
Validate edge capture pipeline reliability, payload correctness, queue policy, retry recovery behavior, and API key authentication.

## Test Types
- Unit tests: queue policy, payload builder, retry decision logic, API key header inclusion.
- Integration tests: `/face/process` contract, API key auth validation, and failure handling.
- Scenario tests: server-down queue/recovery behavior, auth failure behavior.

## Priority Test Areas
1. Payload schema correctness.
2. API key authentication (valid key, missing key, invalid key).
3. Queue max-size/TTL behavior (500 items, 5-min TTL).
4. Non-blocking retry while capture continues.
5. Recovery after backend restart.
6. Edge crop size (~112x112, NOT resized to 160x160).
7. Auth failure handling (401 logged, not queued for retry).

## Exit Criteria
- All critical edge tests pass.
- No blocker/high defects in queue/retry logic.
- API key auth verified (401 on missing/invalid key, 200 on valid key).
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
