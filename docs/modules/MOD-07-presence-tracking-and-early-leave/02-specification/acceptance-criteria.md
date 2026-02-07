# Acceptance Criteria

## Function-Level Acceptance

### FUN-07-01
- Session initializes correctly for valid active schedule/date.
- Invalid session context is rejected.

### FUN-07-02
- Periodic scans update detection state without loop failure.
- Scan interval obeys configured value.

### FUN-07-03
- Consecutive misses increment counter.
- Recovery detection resets counter to zero.

### FUN-07-04
- Early-leave event is flagged when threshold reached.
- Duplicate flags for same context are prevented.

### FUN-07-05
- Presence score calculation matches scan counts.
- Zero-scan case handled safely.

### FUN-07-06
- Presence log endpoint returns scan records for attendance_id.
- Early-leave endpoint returns schedule/date-specific events.

## Module-Level Acceptance
- Early-leave and recovery scenarios behave as documented.
- Presence data aligns with attendance status updates.
- Query endpoints support faculty detail and alert screens.
