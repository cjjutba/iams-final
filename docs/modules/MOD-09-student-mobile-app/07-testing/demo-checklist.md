# Demo Checklist

## Pre-Demo Setup
- [ ] Mobile app has correct `API_BASE_URL` and `WS_BASE_URL` environment values.
- [ ] Backend services for auth, face, schedule, attendance, websocket are running.
- [ ] Student test account and/or registration data source available (seed data in `student_records`).
- [ ] Test student ID available (e.g., `21-A-012345` from seed data).

## Core Functionality
- [ ] Show splash screen → onboarding → welcome routing.
- [ ] Demonstrate student login with valid credentials.
- [ ] Demonstrate session restore on app restart (skip onboarding).
- [ ] Demonstrate 4-step registration flow with validations:
  - [ ] Step 1: Verify student ID (pre-auth, validates against student_records).
  - [ ] Step 2: Account setup with pre-filled fields (pre-auth, returns tokens).
  - [ ] Step 3: Face capture (3-5 images, post-auth with JWT).
  - [ ] Step 4: Review and confirm.
- [ ] Open student home/schedule/history/detail screens.
- [ ] Demonstrate profile edit and face re-registration path.
- [ ] Show student notifications with live events.

## Auth Verification
- [ ] Pre-auth endpoints work without JWT (login, verify-student-id, register).
- [ ] Post-auth endpoints return 401 without JWT.
- [ ] WebSocket rejects connection without valid `token` query param (close code 4001).
- [ ] Expired token triggers refresh attempt.
- [ ] Failed refresh redirects to login screen.

## Data Integrity
- [ ] Attendance timestamps display in Asia/Manila timezone (+08:00).
- [ ] API response fields accessed via snake_case (subject_name, start_time, etc.).
- [ ] Date filters use YYYY-MM-DD format.
- [ ] Error responses handled correctly (no `details` array parsing).

## Screen State Verification
- [ ] Loading states shown during API fetches.
- [ ] Empty states shown when no data available.
- [ ] Error states shown on API failures with retry option.
- [ ] Registration blocks step skipping.

## Connection Reliability
- [ ] WebSocket reconnects after temporary network loss.
- [ ] Notifications update without app restart after reconnect.
- [ ] Connection status indicator shows when disconnected/reconnecting.

## Pass Criteria
- [ ] Student flow is usable end-to-end for MVP.
- [ ] Validation gates block invalid registration progression.
- [ ] All screens have appropriate loading/empty/error states.
- [ ] Notifications update without app restart after reconnect.
- [ ] Tokens stored in SecureStore (verified via developer tools).
