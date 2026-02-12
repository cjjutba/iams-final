# Implementation Plan

## Phase 0: Foundations
- Verify backend API endpoints are functional (auth, schedule, attendance, presence, websocket).
- Verify pre-auth endpoints work without JWT (`/auth/login`, `/auth/forgot-password`).
- Verify post-auth endpoints reject without JWT (401).
- Verify WebSocket endpoint accepts `token` query parameter and returns close codes 4001/4003.
- Configure environment variables (`API_BASE_URL`, `WS_BASE_URL`, `AUTH_STORAGE_KEY`, `TIMEZONE`).
- Verify Axios instance has JWT interceptors (auto-attach Bearer token, 401 refresh handling).
- Verify Expo SecureStore is available and working for token persistence.

## Phase 1: Faculty Auth Foundation
- Implement faculty login screen and API call via `POST /auth/login` (pre-auth).
- Implement forgot password screen via `POST /auth/forgot-password` (pre-auth).
- Implement secure token persistence in Expo SecureStore.
- Implement session restore on app restart (hydrate auth state from SecureStore).
- Guard faculty-only route stack by role/session state.

## Phase 2: Schedule and Live Monitoring
- Implement faculty home and schedule screens via `GET /schedules/me` (post-auth).
- Implement active class resolution using Asia/Manila timezone (+08:00).
- Implement live attendance screen via `GET /attendance/live/{schedule_id}` (post-auth).
- Connect WebSocket via `WS /ws/{user_id}?token=<jwt>` for real-time roster updates.
- Handle WebSocket close codes: 4001 → login redirect, 4003 → error message.

## Phase 3: Manual Attendance and Alert Features
- Implement manual attendance form and submission via `POST /attendance/manual` (post-auth).
- Validate status enum: `present`, `late`, `absent`, `early_leave`.
- Implement early-leave alert screens via `GET /presence/early-leaves` (post-auth).
- Implement class detail and student detail drill-down views.
- Implement class summary/report views.
- Display timestamps in +08:00 timezone, dates as YYYY-MM-DD.

## Phase 4: Profile and Notification Experience
- Implement profile view/edit flows via `GET /auth/me` and `PATCH /users/{id}` (post-auth).
- Use `authService.updateProfile(userId, data)` with userId as first arg.
- Use `authService.changePassword(oldPassword, newPassword)` with two string args.
- Integrate notification feed via WebSocket with event envelope parsing.
- Add reconnect with exponential backoff.
- Show connection status indicator.

## Phase 5: Hardening
- Add consistent loading/empty/error states on all data screens.
- Validate design system compliance (Text weight, Avatar, Divider, colors.status).
- Verify response envelope handling (no `details` array assumed).
- Verify snake_case API field access throughout.
- Validate overall UX readiness.

## Phase 6: Validation
- Run T10 unit/integration/scenario tests.
- Verify pre-auth vs post-auth behavior on all endpoints.
- Verify timezone display on schedule and attendance screens.
- Verify error envelope handling (no `details` array).
- Verify WebSocket close code handling (4001/4003).
- Update traceability and changelog.
