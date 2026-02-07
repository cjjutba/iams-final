# Acceptance Criteria

## Module-Level
- Faculty can login and restore session reliably.
- Faculty can view schedule and monitor a live class end-to-end.
- Manual attendance actions are reflected in live/today views.
- Early-leave alerts and class summaries are visible in faculty screens.
- Profile and notifications flows are functional with reconnect handling.

## Function-Level

### FUN-10-01
- Valid faculty credentials establish session and route to faculty home.
- Session restore works after app restart.

### FUN-10-02
- Faculty schedule renders correctly with active class indicator.
- Empty schedule state is handled gracefully.

### FUN-10-03
- Live roster updates during active class.
- Inactive class state is clear and non-blocking.

### FUN-10-04
- Manual attendance updates succeed for valid payloads.
- Invalid status/fields show clear validation feedback.

### FUN-10-05
- Early-leave alerts render for selected class/date.
- Session summary view reflects backend totals.

### FUN-10-06
- Profile update succeeds and refreshes view state.
- Notifications stream updates and recovers after reconnect.
