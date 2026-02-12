# Implementation Plan

## Phase 0: Foundations
- Verify backend API endpoints are functional (auth, face, schedule, attendance, websocket).
- Verify pre-auth endpoints work without JWT (`/auth/login`, `/auth/register`, `/auth/verify-student-id`).
- Verify post-auth endpoints reject without JWT (401).
- Verify WebSocket endpoint accepts `token` query parameter and returns close codes 4001/4003.
- Configure environment variables (`API_BASE_URL`, `WS_BASE_URL`, `AUTH_STORAGE_KEY`, `TIMEZONE`).
- Set up Axios instance with JWT interceptors (auto-attach Bearer token, 401 refresh handling).
- Verify Expo SecureStore is available and working for token persistence.

## Phase 1: App Entry and Auth Foundation
- Implement splash/onboarding/welcome routing (FUN-09-01, pre-auth).
- Implement student login screen and API call (FUN-09-02, pre-auth → post-auth).
- Implement secure token persistence in Expo SecureStore.
- Implement session restore on app restart (hydrate auth state from SecureStore).
- Implement forgot password screen.

## Phase 2: Registration Workflow
- Implement Step 1: identity verification UI + `POST /auth/verify-student-id` (pre-auth).
- Implement Step 2: account setup UI + `POST /auth/register` (pre-auth, stores returned tokens).
- Implement Step 3: face capture + `POST /face/register` (post-auth, JWT required).
- Implement Step 4: review and confirm.
- Enforce strict step gating — no step skipping.

## Phase 3: Student Portal Views
- Implement home, schedule, history, and detail views (FUN-09-04, post-auth).
- Add consistent loading/empty/error states on all data screens.
- Implement date filters with `YYYY-MM-DD` format.
- Display timestamps in Asia/Manila timezone (+08:00).
- Access API response fields via snake_case.

## Phase 4: Profile and Face Maintenance
- Implement profile view/edit flows (FUN-09-05, post-auth).
- Implement face re-registration and status feedback.
- Use `authService.updateProfile(userId, data)` with userId as first arg.
- Use `authService.changePassword(oldPassword, newPassword)` with two string args.

## Phase 5: Notifications and Hardening
- Integrate student notifications WebSocket flow (FUN-09-06, post-auth).
- Connect via `WS /ws/{user_id}?token=<jwt>` (JWT via query param).
- Handle close codes: 4001 → login redirect, 4003 → error message.
- Add reconnect with exponential backoff.
- Show connection status indicator.
- Validate overall UX readiness and design system compliance.

## Phase 6: Validation
- Run T09 unit/integration/scenario tests.
- Verify pre-auth vs post-auth behavior on all endpoints.
- Verify timezone display on attendance screens.
- Verify error envelope handling (no `details` array).
- Update traceability and changelog.
