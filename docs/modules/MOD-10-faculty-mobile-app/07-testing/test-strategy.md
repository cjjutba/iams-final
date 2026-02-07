# Test Strategy

## Scope
Validate faculty authentication, schedule/live class workflows, manual attendance updates, early-leave visibility, and notification reliability.

## Test Layers
1. Unit tests
- Faculty route guards and auth state handlers
- Manual entry form validators
- Active-class resolution logic
- Notification payload parsing

2. Integration tests
- Auth flow with login/refresh/me endpoints
- Schedule and live attendance data integration
- Manual attendance submission integration
- Presence alert and summary data integration
- WebSocket event integration for faculty screens

3. UI/Scenario tests
- Faculty login to live monitoring flow
- Manual entry reflected in live/today views
- Early-leave alerts and class summary rendering
- Notification reconnect behavior under transient network loss

## Exit Criteria
- All critical `T10-*` tests pass.
- No blocking defects in faculty MVP flow.
