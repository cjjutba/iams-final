# Test Cases

## Unit Tests
- `T08-U1`: Reject websocket connection with invalid token.
- `T08-U2`: Reject websocket when path `user_id` mismatches token subject.
- `T08-U3`: Build valid `attendance_update` envelope.
- `T08-U4`: Build valid `early_leave` envelope.
- `T08-U5`: Build valid `session_end` envelope.
- `T08-U6`: Remove stale connection on heartbeat timeout.

## Integration Tests
- `T08-I1`: Connect authenticated client and receive attendance update.
- `T08-I2`: Receive early-leave event from presence trigger source.
- `T08-I3`: Receive session-end summary payload.
- `T08-I4`: Disconnect/reconnect and resume stream.
- `T08-I5`: Failed send path logs and cleans stale socket.

## Scenario Tests
- `T08-S1`: Faculty live screen updates roster in real time.
- `T08-S2`: Faculty notifications screen shows early-leave alert item.
- `T08-S3`: Student notifications screen receives routed session-end update.
- `T08-S4`: Multiple reconnect cycles do not duplicate connection map entries.

## Performance/Resilience
- `T08-P1`: Measure average event latency under target threshold.
- `T08-P2`: Simulate intermittent network loss for 5 minutes and verify recovery.
