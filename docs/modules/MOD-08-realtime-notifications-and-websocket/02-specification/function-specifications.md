# Function Specifications

## FUN-08-01 Open Authenticated WebSocket Connections
Goal:
- Accept only authenticated clients and bind each connection to a verified user identity.

Inputs:
- Path param `user_id`, auth token from handshake context.

Process:
1. Parse and validate `user_id`.
2. Validate token and resolve authenticated principal.
3. Reject if principal does not match path `user_id`.
4. Register socket in connection map.

Outputs:
- Active websocket session bound to user.

Validation Rules:
- Reject invalid token.
- Reject user mismatch.
- Do not create duplicate stale entries for reconnects.

## FUN-08-02 Publish Attendance Update Events
Goal:
- Push attendance changes to relevant connected clients.

Inputs:
- Attendance status change payload from attendance flow.

Process:
1. Build event envelope of type `attendance_update`.
2. Resolve target recipients.
3. Send payload to active sockets.
4. Record delivery metadata if logging is enabled.

Outputs:
- Delivered attendance update events.

Validation Rules:
- Payload must include required fields.
- Silent drop is not allowed; failures must be logged.

## FUN-08-03 Publish Early-Leave Events
Goal:
- Push early-leave alerts as soon as threshold logic flags a student.

Inputs:
- Early-leave event payload from presence flow.

Process:
1. Build event envelope of type `early_leave`.
2. Resolve faculty and related notification recipients.
3. Send to active connections.
4. Log delivery outcome if enabled.

Outputs:
- Delivered early-leave alert events.

Validation Rules:
- Event must contain student and schedule context.
- Duplicate emission for same event ID should be prevented when dedup key exists.

## FUN-08-04 Publish Session-End Summary Events
Goal:
- Push summary counts when a class session ends.

Inputs:
- Session completion data (schedule + summary counts).

Process:
1. Build event envelope of type `session_end`.
2. Resolve recipients for class context.
3. Send summary to active clients.

Outputs:
- Delivered session-end summary events.

Validation Rules:
- Summary must include status totals.
- Session end should be emitted once per schedule/date session.

## FUN-08-05 Handle Reconnect and Stale Connection Cleanup
Goal:
- Maintain healthy connection map across disconnects, app backgrounding, and network loss.

Inputs:
- Disconnect signals, send failures, heartbeat timeouts, reconnect attempts.

Process:
1. Detect disconnected or unresponsive sockets.
2. Remove stale entries from map.
3. Accept reconnect and rebind to user.
4. Resume event fanout to latest active socket(s).

Outputs:
- Clean connection map and stable reconnect behavior.

Validation Rules:
- Cleanup must not remove active healthy sockets.
- Reconnect should not create unbounded duplicate entries.
