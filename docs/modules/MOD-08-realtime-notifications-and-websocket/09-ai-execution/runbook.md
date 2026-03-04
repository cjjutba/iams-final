# AI Runbook (MOD-08)

## Step-by-Step
1. Select one `FUN-08-*` target.
2. Open function spec and event contract docs.
3. Implement minimum compliant behavior in backend/mobile scope.
4. Run relevant tests for the change.
5. Update traceability matrix if mappings changed.
6. Record contract changes before expanding scope.

## Guardrails
- No undocumented event types.
- No payload contract drift without docs update.
- No unauthenticated websocket acceptance.
- No merge with known stale-connection leak behavior.
