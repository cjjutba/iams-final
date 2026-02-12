# Acceptance Criteria

## Module-Level
- Student can move from app entry to authenticated home flow.
- Registration enforces step validation and blocks invalid progression.
- Pre-auth endpoints work without JWT; post-auth endpoints reject without JWT.
- Dashboard/history/profile screens render with robust UI states (loading/empty/error).
- All timestamps display in Asia/Manila timezone (+08:00).
- Notification screen updates from realtime stream and survives reconnect.
- Tokens stored in Expo SecureStore, never in AsyncStorage or logs.
- Error responses handled per HTTP envelope format (no `details` array assumed).

## Function-Level

### FUN-09-01 (Onboarding)
- First-time users see onboarding slides.
- Returning users with valid session skip onboarding and route to student home.
- No API calls made during onboarding — purely local navigation.

### FUN-09-02 (Login and Session)
- `POST /auth/login` callable without JWT (pre-auth).
- Login success stores tokens in Expo SecureStore.
- `GET /auth/me` requires JWT in Authorization header (post-auth).
- Invalid or expired session is handled gracefully (refresh attempt, then login redirect).
- Error response uses `{ "success": false, "error": { "code", "message" } }` format.

### FUN-09-03 (Registration)
- Step 1: `POST /auth/verify-student-id` works without JWT (pre-auth).
- Step 1: Validates against `student_records` table; rejects unknown/duplicate IDs.
- Step 1: Returns profile snapshot (name, course, year, section, email) on success.
- Step 2: `POST /auth/register` works without JWT (pre-auth).
- Step 2: Returns `access_token` and `refresh_token` on success.
- Step 3: `POST /face/register` requires JWT (post-auth).
- Step 3: Requires valid 3-5 face images before continue.
- Step 4: Review screen confirms all data before completion.
- All four registration steps are required — no step skipping.

### FUN-09-04 (Attendance Dashboard)
- All endpoints (`/schedules/me`, `/attendance/me`, `/attendance/today`) require JWT.
- Home/history/detail data reflects backend response accurately.
- Timestamps display in Asia/Manila timezone format.
- Empty/error states are visible and non-blocking.
- API response fields accessed via snake_case (e.g., `subject_name`).

### FUN-09-05 (Profile and Face)
- `GET /auth/me`, `PATCH /users/{id}`, `/face/status`, `/face/register` all require JWT.
- Profile edits persist successfully via PATCH endpoint.
- Face re-registration requires 3-5 valid images.
- `authService.updateProfile(userId, data)` called with userId as first arg.
- `authService.changePassword(oldPassword, newPassword)` called with two string args.

### FUN-09-06 (Notifications)
- WebSocket connects via `WS /ws/{user_id}?token=<jwt>` (JWT via query param).
- Incoming events appear in notifications list formatted by type.
- Close code 4001 → redirect to login screen.
- Close code 4003 → show permission error message.
- Temporary network loss recovers via reconnect with exponential backoff.
- Unknown event types are safely ignored (no crash).
- Timestamps in events use ISO-8601 with +08:00 offset.
