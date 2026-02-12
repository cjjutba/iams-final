# Function Specifications

## FUN-09-01 Onboarding and Welcome Flow
- **Type**: Pre-auth (local navigation only)
- **Auth**: None required

Goal:
- Guide first-time users and route them to student or faculty entry paths.

Inputs:
- First-launch flag (AsyncStorage), saved auth/session state (SecureStore).

Process:
1. Show splash and evaluate startup state.
2. Check for persisted auth tokens in SecureStore.
3. If tokens exist and valid → skip to student home (post-auth).
4. If first launch → show onboarding slides.
5. Navigate to welcome screen for role selection.
6. Route student selection to student login/register path.

Outputs:
- Correct starting route for student user journey.

Validation Rules:
- Onboarding should not block returning authenticated users.
- Navigation transitions must be deterministic and testable.
- No API calls required — purely local state evaluation.

## FUN-09-02 Student Login and Token Persistence
- **Type**: Pre-auth → Post-auth transition
- **Auth**: Pre-auth: `POST /auth/login` (no JWT). Post-auth: tokens stored for subsequent calls.

Goal:
- Authenticate student and persist session securely across app restarts.

Inputs:
- Student credentials (email + password).
- Backend auth API responses.

Process:
1. Submit login request to `POST /api/v1/auth/login` (no JWT required).
2. Receive response envelope: `{ "success": true, "data": { "access_token", "refresh_token", "token_type", "expires_in" } }`.
3. Store tokens in Expo SecureStore (never AsyncStorage).
4. Fetch current user profile via `GET /api/v1/auth/me` (JWT required).
5. Hydrate authStore with user identity and token metadata.
6. On app restart: load tokens from SecureStore → validate → hydrate state.

Outputs:
- Active authenticated student session.

Validation Rules:
- Invalid credentials → show error from backend `error.message` field.
- Expired token → attempt `POST /auth/refresh`, fallback to login screen.
- Error response format: `{ "success": false, "error": { "code": "...", "message": "..." } }` — no `details` array.

## FUN-09-03 Four-Step Student Registration
- **Type**: Pre-auth (Steps 1-2) → Post-auth (Steps 3-4)
- **Auth**: Steps 1-2 require no JWT. Steps 3-4 use JWT from registration response.

Goal:
- Complete student registration with strict validation gates.

Inputs:
- Step 1: student ID string.
- Step 2: email, password, confirm_password (pre-filled name/course/year/section from Step 1 response).
- Step 3: 3-5 face images captured via device camera.
- Step 4: confirmation/review of all data.

Process:
1. **Step 1** (`SCR-007`): Submit `POST /api/v1/auth/verify-student-id` (pre-auth). Backend validates against `student_records` table. Returns student profile snapshot (name, course, year, section, email) on success.
2. **Step 2** (`SCR-008`): Pre-fill fields from Step 1 snapshot. Collect password. Submit `POST /api/v1/auth/register` (pre-auth). On success, receive `access_token` and `refresh_token` — store in SecureStore. User is now authenticated.
3. **Step 3** (`SCR-009`): Capture 3-5 face images via camera. Submit `POST /api/v1/face/register` (post-auth, JWT required). Backend generates FaceNet embeddings and stores in FAISS.
4. **Step 4** (`SCR-010`): Review all captured data. Confirm registration complete. Navigate to student home.

Outputs:
- Registered student account with linked face registration.

Validation Rules:
- No step skipping — each step must complete before the next enables.
- Step 1: student ID must match `student_records` table entry.
- Step 1: duplicate registration (same student_id already registered) is rejected.
- Step 3: face upload requires minimum 3 images, maximum 5.
- Face registration rejects invalid/undetectable images.
- Draft data persists locally during session, cleared on submit or cancel.

## FUN-09-04 Attendance Dashboard and History
- **Type**: Post-auth
- **Auth**: All endpoints require `Authorization: Bearer <token>` header.

Goal:
- Show student attendance status, class schedule, and historical records.

Inputs:
- Authenticated user context (JWT from SecureStore).
- Responses from `GET /schedules/me`, `GET /attendance/me`, `GET /attendance/today`.

Process:
1. Fetch schedule via `GET /api/v1/schedules/me` (JWT required).
2. Fetch attendance history via `GET /api/v1/attendance/me?start_date=...&end_date=...` (JWT required).
3. Fetch today's attendance context via `GET /api/v1/attendance/today?schedule_id=<uuid>` (JWT required).
4. Render data with loading, empty, and error states per screen.
5. Display timestamps formatted in Asia/Manila timezone (+08:00).

Outputs:
- Student-facing attendance insights across home/history/detail screens.

Validation Rules:
- Date filters and sorting must be stable.
- Unauthorized (401) responses → attempt refresh, fallback to login.
- API response fields use snake_case: `subject_name`, `start_time`, `room_name`, `attendance_status`.
- Empty states show appropriate messages and CTAs.

## FUN-09-05 Profile and Face Re-Registration
- **Type**: Post-auth
- **Auth**: All endpoints require `Authorization: Bearer <token>` header.

Goal:
- Allow student to manage profile fields and renew face registration.

Inputs:
- Profile data from `GET /auth/me`.
- Profile edits for `PATCH /users/{id}`.
- Face status from `GET /face/status`.
- New face captures for `POST /face/register`.

Process:
1. Load profile from `GET /api/v1/auth/me` (JWT required).
2. Display profile fields; allow editing on `SCR-016`.
3. Submit validated edits via `PATCH /api/v1/users/{id}` (JWT required). Note: `authService.updateProfile(userId, data)` — userId is required as first arg.
4. Check face status via `GET /api/v1/face/status` (JWT required).
5. If re-registration requested, capture 3-5 face images and submit via `POST /api/v1/face/register` (JWT required).

Outputs:
- Updated profile and refreshed face registration state.

Validation Rules:
- Profile field validation must match backend constraints.
- Re-registration requires authenticated student context (JWT).
- `authService.changePassword(oldPassword, newPassword)` — two string args, not an object.
- Show success/error feedback after profile or face update.

## FUN-09-06 Student Notifications
- **Type**: Post-auth
- **Auth**: WebSocket requires JWT via `token` query parameter.

Goal:
- Display notification events and keep feed updated in realtime.

Inputs:
- WebSocket event stream from `WS /ws/{user_id}?token=<jwt>`.
- Optional notification cache from local storage.

Process:
1. Connect WebSocket for authenticated user: `ws://<host>/api/v1/ws/{user_id}?token=<jwt>`.
2. Receive event envelope: `{ "type": "attendance_update|session_end|early_leave", "data": { ... } }`.
3. Parse and render event items by type in notification feed.
4. On disconnect: show reconnecting indicator, use exponential backoff.
5. On close code 4001 (Unauthorized): redirect to login screen.
6. On close code 4003 (Forbidden): show permission error message.
7. On successful reconnect: resume stream without app restart.

Outputs:
- Live student notification feed on SCR-018.

Validation Rules:
- Feed must not crash on unknown/invalid payload — ignore unknown event types.
- Reconnect path must recover without app restart.
- Student receives: `attendance_update`, `session_end`, optionally `early_leave` (based on backend routing).
- Timestamps in event data use ISO-8601 with +08:00 offset.
