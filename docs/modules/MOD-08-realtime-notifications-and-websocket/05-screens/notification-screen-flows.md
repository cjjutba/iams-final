# Notification Screen Flows

## Faculty Live Attendance Flow (SCR-021)
1. Screen opens and requests current live class context.
2. App opens WebSocket connection.
3. On `attendance_update`, roster item status updates immediately.
4. On `early_leave`, alert banner/list item appears.
5. On `session_end`, summary card is shown and live state closes.

## Faculty Notification Feed Flow (SCR-029)
1. Screen opens and subscribes to event stream.
2. Incoming events append to feed in reverse-chronological order.
3. If disconnected, UI shows reconnecting state.
4. On reconnect, feed resumes realtime updates.

## Student Notification Flow (SCR-018)
1. Screen opens and subscribes to user-scoped notifications.
2. Incoming events are rendered by type with timestamp.
3. On reconnect, connection-state indicator clears when healthy.

## Failure/Recovery Flow
1. Network drops while screen active.
2. UI switches to reconnecting state.
3. Client retries connection with backoff.
4. Once connected, new events resume without app restart.
