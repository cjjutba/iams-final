# Test Cases

## Unit Tests
- `T08-U1`: Reject WebSocket connection with invalid token → close code 4001.
- `T08-U2`: Reject WebSocket when path `user_id` mismatches JWT `sub` → close code 4003.
- `T08-U3`: Build valid `attendance_update` envelope with required fields and timezone offset.
- `T08-U4`: Build valid `early_leave` envelope with required fields and timezone offset.
- `T08-U5`: Build valid `session_end` envelope with summary counts.
- `T08-U6`: Remove stale connection on heartbeat timeout (no pong within `WS_STALE_TIMEOUT`).
- `T08-U7`: Reject WebSocket connection with missing `token` query parameter → close code 4001.
- `T08-U8`: Reject WebSocket connection with expired JWT → close code 4001.
- `T08-U9`: Validate event envelope rejects unknown `type` values.

## Integration Tests
- `T08-I1`: Connect authenticated client and receive `attendance_update` event.
- `T08-I2`: Receive `early_leave` event from presence trigger source (MOD-07).
- `T08-I3`: Receive `session_end` summary payload with correct count fields.
- `T08-I4`: Disconnect/reconnect and resume stream (idempotent — no duplicate entries).
- `T08-I5`: Failed send path logs error and cleans stale socket.
- `T08-I6`: Reconnect evicts stale entry for same `user_id` before registering new.
- `T08-I7`: Event timestamps include timezone offset (`+08:00`).
- `T08-I8`: Student client receives routed `session_end` but not `early_leave` (faculty-targeted).

## Scenario Tests
- `T08-S1`: Faculty live screen (SCR-021) updates roster in real time on `attendance_update`.
- `T08-S2`: Faculty notifications screen (SCR-029) shows early-leave alert item.
- `T08-S3`: Student notifications screen (SCR-018) receives routed session-end update.
- `T08-S4`: Multiple reconnect cycles do not duplicate connection map entries.
- `T08-S5`: Auth error (4001) on expired JWT triggers redirect to login screen.

## Performance/Resilience
- `T08-P1`: Measure average event latency under target threshold.
- `T08-P2`: Simulate intermittent network loss for 5 minutes and verify recovery.
