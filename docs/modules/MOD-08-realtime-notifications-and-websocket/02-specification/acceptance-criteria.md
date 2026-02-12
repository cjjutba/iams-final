# Acceptance Criteria

## Module-Level
- `WS /ws/{user_id}` accepts only authenticated user-matching connections.
- Missing/invalid/expired JWT → close code 4001 (Unauthorized).
- `user_id` mismatch with JWT `sub` → close code 4003 (Forbidden).
- Event payloads for `attendance_update`, `early_leave`, and `session_end` match documented schemas.
- Event envelope format: `{ "type": "...", "data": { ... } }`.
- All event timestamps include timezone offset (`+08:00`).
- Disconnect and reconnect sequence recovers live updates without app restart.
- Stale connections are removed and do not receive future fanout.
- System-internal functions (FUN-08-02 to FUN-08-04) do not expose HTTP/WS endpoints.

## Function-Level

### FUN-08-01
- Valid authenticated client connects successfully and is registered in connection map.
- Invalid/expired token → connection rejected with close code 4001.
- User mismatch → connection rejected with close code 4003.
- Reconnect evicts stale entry for same `user_id` before registering new socket.

### FUN-08-02
- Attendance update event is delivered to connected recipients (faculty for schedule, student for own record).
- Payload contains required fields: `student_id`, `status`, `timestamp`.
- Missing required payload fields cause logged validation failure (not silent drop).
- Timestamp includes timezone offset.

### FUN-08-03
- Early-leave alert event is delivered to faculty recipients in active session context.
- Payload contains required fields: `student_id`, `schedule_id`, `detected_at`.
- Duplicate alert emission is prevented when dedup key exists.
- Timestamp includes timezone offset.

### FUN-08-04
- Session-end summary is delivered with correct count fields (`present`, `late`, `early_leave`, `absent`).
- Event emitted once per ended schedule/date session.
- Both faculty and enrolled students receive the event.

### FUN-08-05
- Reconnect after temporary network loss resumes updates via new authenticated connection.
- Stale map entries are removed on heartbeat timeout/disconnect.
- No unbounded duplicate entries after repeated reconnect cycles.
- Active healthy sockets are not prematurely removed.
