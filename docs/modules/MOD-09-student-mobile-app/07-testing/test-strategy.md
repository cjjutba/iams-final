# Test Strategy

## Scope
Validate student onboarding, registration, authenticated data views, profile management, notification behavior, auth flow correctness, timezone display, and error handling.

## Test Layers

### 1. Unit Tests
- Form validators and step guards (registration step progression)
- Store reducers/actions and state transitions (Zustand stores)
- Session persistence helpers (SecureStore read/write)
- Auth token validation and refresh logic
- Timestamp formatting (Asia/Manila timezone)
- Event envelope parsing (unknown type handling)

### 2. Integration Tests
- Auth flow: login → token persistence → session restore → refresh
- Registration step API chain: verify-student-id → register → face register
- Pre-auth vs post-auth endpoint behavior (401 on missing JWT)
- Attendance/schedule screen data fetch integration
- Profile update round-trip via PATCH endpoint
- Face re-registration status update flow
- WebSocket connect/reconnect with JWT via query param
- WebSocket close code handling (4001 → login, 4003 → error)

### 3. UI/Scenario Tests
- First launch onboarding and welcome routing
- Full student registration end-to-end (4 steps)
- Returning user session restore (skip onboarding)
- Attendance history and detail navigation with date filters
- Profile update and face re-registration path
- Reconnect behavior in notification screen
- Auth error recovery (401 → refresh → login redirect)
- Timestamp display verification (Asia/Manila +08:00)

## Priority Areas
1. Registration step validation and gating (no step skip)
2. Pre-auth vs post-auth endpoint behavior
3. Token persistence and refresh flow
4. WebSocket auth (JWT via query param, close codes)
5. Error envelope handling (no `details` array)
6. Timezone display accuracy
7. Design system constraint compliance
8. UI state triad (loading/empty/error) on all data screens
9. Offline/reconnect behavior

## Exit Criteria
- All critical `T09-*` tests pass.
- No blocking defects in student MVP journey.
- Pre-auth and post-auth endpoints behave correctly.
- Timestamps display in correct timezone format.
