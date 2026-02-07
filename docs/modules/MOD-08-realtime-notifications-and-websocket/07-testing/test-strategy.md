# Test Strategy

## Scope
Validate socket auth, event payload correctness, fanout behavior, and reconnect stability.

## Test Layers
1. Unit tests
- Connection manager lifecycle logic
- Payload validator for each event type
- Cleanup and stale detection logic

2. Integration tests
- `WS /ws/{user_id}` auth acceptance/rejection
- End-to-end event emission from service to socket client

3. Scenario tests
- Attendance update appears in live faculty screen
- Early-leave alert appears during active class
- Session-end summary appears at class completion
- Network drop and reconnect recovery

4. Performance checks
- WebSocket latency target under documented threshold (see main testing docs)
- No connection map leak after repeated reconnect cycles

## Entry and Exit Criteria
- Entry: prerequisites modules stable (`MOD-01`, `MOD-06`, `MOD-07`).
- Exit: all critical T08 tests passing and no major reconnect defects.
