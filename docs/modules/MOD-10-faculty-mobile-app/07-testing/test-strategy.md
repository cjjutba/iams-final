# Test Strategy

## Scope
Validate faculty authentication, schedule/live class workflows, manual attendance updates, early-leave visibility, notification reliability, auth enforcement, timezone display, error envelope handling, and design system compliance.

## Test Layers

### 1. Unit Tests
- Faculty route guards and auth state handlers
- Manual entry form validators (status enum, required fields)
- Active-class resolution logic (timezone-aware)
- Notification payload parsing (event envelope)
- Timestamp formatter (+08:00 display)
- Error envelope parser (no `details` array assumption)
- SecureStore token persistence helpers

### 2. Integration Tests
- Auth flow with login/refresh/me endpoints (pre-auth → post-auth)
- Schedule and live attendance data integration
- Manual attendance submission and response handling
- Presence alert and summary data integration
- WebSocket event integration for faculty screens
- Pre-auth endpoint access without JWT
- Post-auth endpoint rejection without JWT (401)
- WebSocket close code handling (4001, 4003)

### 3. UI/Scenario Tests
- Faculty login to live monitoring flow (end-to-end)
- Manual entry reflected in live/today views
- Early-leave alerts and class summary rendering
- Notification reconnect behavior under transient network loss
- Token refresh failure → login redirect
- Timezone display correctness on attendance screens

## Priority Areas
1. Faculty auth flow (login, refresh, session restore)
2. Live attendance monitoring with WebSocket
3. Manual attendance submission and validation
4. Early-leave alert visibility
5. WebSocket reconnect and close code handling
6. Pre-auth vs post-auth endpoint enforcement
7. Timezone display (+08:00)
8. Error envelope parsing (no `details` array)
9. Design system constraint adherence

## Exit Criteria
- All critical `T10-*` tests pass.
- No blocking defects in faculty MVP flow.
- Auth enforcement verified (pre-auth vs post-auth).
- Timezone display verified on attendance screens.
