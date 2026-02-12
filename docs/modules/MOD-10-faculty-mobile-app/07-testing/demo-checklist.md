# Demo Checklist

## Pre-Demo Setup
- [ ] Faculty test account is pre-seeded and active (faculty@gmail.com / password123).
- [ ] Mobile app has correct API/WS environment values.
- [ ] Backend modules for auth/schedule/attendance/presence/websocket are running.
- [ ] At least one schedule exists for the faculty user on the current day.

## Core Functionality
- [ ] Login as faculty and verify session restore behavior.
- [ ] Show faculty home/schedule and active class selection.
- [ ] Open live attendance and demonstrate realtime updates.
- [ ] Perform manual attendance update and verify reflected change.
- [ ] Show early-leave alerts and class summary visibility.
- [ ] Show faculty profile view and edit flow.
- [ ] Show faculty notifications and reconnect behavior.

## Auth Verification
- [ ] Faculty login works without JWT (pre-auth).
- [ ] Forgot password screen accessible without JWT.
- [ ] All portal screens require JWT — redirect to login if missing.
- [ ] Token refresh works when access token expires.
- [ ] Refresh failure clears session and redirects to login.
- [ ] WebSocket connects with `?token=<jwt>` query param.
- [ ] WebSocket close code 4001 triggers login redirect.

## Data Integrity
- [ ] Schedule times display in Asia/Manila timezone (+08:00).
- [ ] Attendance timestamps show +08:00 offset.
- [ ] Manual entry date uses YYYY-MM-DD format.
- [ ] API response fields accessed via snake_case names.
- [ ] Response envelope parsed correctly (no `details` array assumed).

## Screen State Verification
- [ ] Loading skeletons visible during data fetch.
- [ ] Empty states shown when no classes/alerts/notifications exist.
- [ ] Error states shown on API failure with retry option.
- [ ] Form draft preserved on submission error.

## Connection Reliability
- [ ] WebSocket reconnect indicator visible during disconnect.
- [ ] Reconnect with exponential backoff after network loss.
- [ ] Live updates resume after reconnect without app restart.

## Pass Criteria
- [ ] Faculty can monitor and control attendance end-to-end.
- [ ] Manual updates and alerts are visible in expected screens.
- [ ] Realtime updates recover after reconnect without app restart.
- [ ] All timestamps display in +08:00 timezone.
- [ ] All auth flows work correctly (pre-auth vs post-auth).
