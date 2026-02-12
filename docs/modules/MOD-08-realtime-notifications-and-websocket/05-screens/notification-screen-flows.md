# Notification Screen Flows

## Faculty Live Attendance Flow (SCR-021)
**Auth:** Authenticated faculty (Supabase JWT).
1. Screen opens and requests current live class context via REST API.
2. App opens WebSocket connection (`WS /ws/{user_id}?token=<jwt>`).
3. On `attendance_update`, roster item status updates immediately.
4. On `early_leave`, alert banner/list item appears.
5. On `session_end`, summary card is shown and live state closes.
6. Pull-to-refresh: re-fetch current state via REST, WebSocket continues.

## Faculty Early-Leave Alerts Flow (SCR-025)
**Auth:** Authenticated faculty (Supabase JWT).
1. Screen opens and subscribes to event stream.
2. On `early_leave`, alert card appears with student name and detection time.
3. If disconnected, UI shows reconnecting state.
4. On reconnect, new alerts resume without app restart.

## Faculty Notification Feed Flow (SCR-029)
**Auth:** Authenticated faculty (Supabase JWT).
1. Screen opens and subscribes to event stream.
2. Incoming events append to feed in reverse-chronological order.
3. If disconnected, UI shows reconnecting state.
4. On reconnect, feed resumes realtime updates.
5. Pull-to-refresh: re-fetch recent notifications via REST.

## Student Notification Flow (SCR-018)
**Auth:** Authenticated student (Supabase JWT).
1. Screen opens and subscribes to user-scoped notifications.
2. Incoming events are rendered by type with timestamp (timezone offset displayed).
3. On reconnect, connection-state indicator clears when healthy.
4. Pull-to-refresh: re-fetch recent notifications via REST.

## Failure/Recovery Flow
1. Network drops while screen active.
2. UI switches to reconnecting badge/indicator.
3. Client retries connection with exponential backoff (`WS_RECONNECT_BASE_DELAY_MS` to `WS_RECONNECT_MAX_DELAY_MS`).
4. Once connected, new events resume without app restart.

## Auth Error Handling
- **Close code 4001 (Unauthorized):** Redirect to login screen. Show "Session expired" toast.
- **Close code 4003 (Forbidden):** Show error message. Do not redirect (likely a client bug).
- **Repeated reconnect failures:** After `WS_RECONNECT_MAX_ATTEMPTS` (0 = infinite), show persistent error banner.
