# Test Strategy

## Scope
Validate student onboarding, registration, authenticated data views, profile management, and notification behavior.

## Test Layers
1. Unit tests
- Form validators and step guards
- Store reducers/actions and state transitions
- Session persistence helpers

2. Integration tests
- Auth flow with login/refresh/me path
- Registration step API integration
- Attendance/schedule screen data fetch integration
- WebSocket feed integration for student notifications

3. UI/Scenario tests
- First launch onboarding and welcome routing
- Full student registration end-to-end
- Attendance history and detail navigation
- Profile update and face re-registration path
- Reconnect behavior in notification screen

## Exit Criteria
- All critical `T09-*` tests pass.
- No blocking defects in student MVP journey.
