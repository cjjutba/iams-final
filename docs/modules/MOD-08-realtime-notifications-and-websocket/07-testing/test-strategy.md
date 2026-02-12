# Test Strategy

## Scope
Validate WebSocket auth, event payload correctness, fanout behavior, reconnect stability, timezone formatting, and error handling.

## Test Layers

### 1. Unit Tests
- Connection manager lifecycle logic (register, evict, cleanup)
- JWT validation for WebSocket handshake (valid, invalid, expired, mismatch)
- Payload builder and validator for each event type
- Cleanup and stale detection logic
- Event envelope format validation
- Close code verification (4001, 4003)

### 2. Integration Tests
- `WS /ws/{user_id}` auth acceptance/rejection with real JWT tokens
- End-to-end event emission from service to socket client
- Event delivery with timezone-aware timestamps
- Failed send logging and stale cleanup
- Idempotent reconnect behavior

### 3. Scenario Tests
- Attendance update appears in live faculty screen
- Early-leave alert appears during active class
- Session-end summary appears at class completion
- Network drop and reconnect recovery
- Auth redirect on expired JWT during WS session

### 4. Performance/Resilience Checks
- WebSocket latency target under documented threshold
- No connection map leak after repeated reconnect cycles
- Connection cap enforcement (`WS_MAX_CONNECTIONS_PER_USER`)

## Priority Areas
1. JWT auth validation (close codes 4001/4003)
2. Event envelope format and required fields
3. Reconnect idempotency (no duplicate entries)
4. Stale connection cleanup
5. Timezone-aware timestamps in events
6. Send failure logging (no silent drops)
7. Event dedup (early_leave context)
8. User deletion → WS disconnect
9. Connection cap enforcement

## Entry and Exit Criteria
- Entry: prerequisite modules stable (`MOD-01` JWT, `MOD-06` attendance events, `MOD-07` early-leave events).
- Exit: all critical T08 tests passing, no major reconnect defects, auth enforcement verified.
