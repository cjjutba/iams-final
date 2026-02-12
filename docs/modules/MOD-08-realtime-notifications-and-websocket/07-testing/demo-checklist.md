# Demo Checklist

## Pre-Demo Setup
- [ ] Backend running with WebSocket endpoint enabled.
- [ ] Mobile app connected to correct `WS_BASE_URL`.
- [ ] At least one faculty client and one student client ready.
- [ ] Seed data includes schedules, enrollments, and active sessions.
- [ ] `TIMEZONE` configured to Asia/Manila.

## 1. Core Functionality
- [ ] Open faculty live attendance screen (`SCR-021`).
- [ ] Trigger attendance update and verify realtime roster update.
- [ ] Trigger early-leave event and verify alert appears on SCR-021 and SCR-025.
- [ ] End session and verify session-end summary event is shown.
- [ ] Student notification screen (`SCR-018`) receives session-end event.

## 2. Auth Verification
- [ ] Connect with valid JWT — connection accepted.
- [ ] Attempt connection with invalid JWT — rejected with close code 4001.
- [ ] Attempt connection with expired JWT — rejected with close code 4001.
- [ ] Attempt connection with mismatched `user_id` — rejected with close code 4003.

## 3. Connection Reliability
- [ ] Disable network briefly and verify reconnect behavior after restore.
- [ ] Reconnect does not create duplicate connection map entries.
- [ ] No app restart needed to resume updates after reconnect.
- [ ] Stale connection is cleaned up after heartbeat timeout.

## 4. Data Integrity
- [ ] All three event types observed with valid payload fields.
- [ ] Event timestamps include timezone offset (`+08:00`).
- [ ] No duplicate spam events caused by reconnect.
- [ ] Early-leave event not re-emitted for same attendance context.

## 5. Screen Integration
- [ ] SCR-021 (FacultyLiveAttendance) shows all 3 event types.
- [ ] SCR-025 (FacultyEarlyLeaveAlerts) shows early-leave events.
- [ ] SCR-029 (FacultyNotifications) shows all 3 event types in feed.
- [ ] SCR-018 (StudentNotifications) shows session-end and routed events.
- [ ] Reconnecting badge appears on all screens during network drop.

## 6. Error Handling
- [ ] Auth error (4001) redirects to login screen.
- [ ] Send failure logged (not silently dropped).
- [ ] Malformed event payload not emitted to clients.

## Pass Criteria
- All items above checked.
- No unresolved connection leaks or duplicate events.
- Auth enforcement working for all close code scenarios.
