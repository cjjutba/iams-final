# Acceptance Criteria

## Module-Level
- `WS /ws/{user_id}` accepts only authenticated user-matching connections.
- Event payloads for `attendance_update`, `early_leave`, and `session_end` match docs.
- Disconnect and reconnect sequence recovers live updates.
- Stale connections are removed and do not receive future fanout.

## Function-Level

### FUN-08-01
- Valid authenticated client connects successfully.
- Invalid token or user mismatch is rejected.

### FUN-08-02
- Attendance update event is delivered to connected recipients.
- Missing required payload fields cause validation/logged failure.

### FUN-08-03
- Early-leave alert event is delivered in active session context.
- Duplicate alert emission is prevented when dedup key exists.

### FUN-08-04
- Session-end summary is delivered with correct count fields.
- Event emitted once per ended session.

### FUN-08-05
- Reconnect after temporary network loss resumes updates.
- Stale map entries are removed on timeout/disconnect.
