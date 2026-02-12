# Student App Screen Flows

## Entry and Auth Flow (Pre-Auth)
1. `SCR-001` Splash evaluates first launch and session state.
   - If tokens in SecureStore and valid → skip to student home (post-auth).
   - If no tokens → continue to onboarding/welcome.
2. New users go to `SCR-002` Onboarding, then `SCR-003` Welcome.
3. Student route goes to `SCR-004` StudentLogin or registration flow.
4. Forgot password path uses `SCR-006`.

**Auth context**: All screens in this flow are pre-auth (no JWT required).

## Registration Flow (Pre-Auth → Post-Auth, 4 Steps)
1. `SCR-007` (Step 1): Verify student ID via `POST /auth/verify-student-id` (pre-auth). Backend validates against `student_records` table. Returns profile snapshot on success.
2. `SCR-008` (Step 2): Collect account details (pre-filled from Step 1). Submit `POST /auth/register` (pre-auth). On success: receive tokens → store in SecureStore → user is now authenticated.
3. `SCR-009` (Step 3): Capture 3-5 face images via camera. Submit `POST /face/register` (post-auth, JWT required from Step 2).
4. `SCR-010` (Step 4): Review all data and confirm registration. Navigate to student home.

**Auth transition**: Steps 1-2 are pre-auth. Steps 3-4 are post-auth (JWT from registration response).

## Student Portal Flow (Post-Auth)
1. After auth, land on `SCR-011` StudentHome.
2. Navigate to `SCR-012` schedule and `SCR-013` history.
3. Open detailed record in `SCR-014`.
4. Manage profile via `SCR-015` and `SCR-016`.
5. Re-register face via `SCR-017`.
6. View notifications in `SCR-018`.

**Auth context**: All portal screens require valid JWT. On 401 → refresh attempt → login redirect.

## Realtime Notification Flow (Post-Auth)
1. On `SCR-018`, connect WebSocket: `ws://<host>/api/v1/ws/{user_id}?token=<jwt>`.
2. Receive event envelope: `{ "type": "...", "data": { ... } }`.
3. Render incoming event cards by type (`attendance_update`, `session_end`, `early_leave`).
4. On disconnect: show reconnecting indicator, use exponential backoff.
5. On close code 4001 (Unauthorized): redirect to login screen.
6. On close code 4003 (Forbidden): show permission error.
7. Resume updates after reconnect without app restart.

## Auth Error Handling
- **401 from any post-auth endpoint**: Attempt `/auth/refresh`, if fails → redirect to `SCR-004` (login).
- **WebSocket close code 4001**: Redirect to `SCR-004` (login).
- **WebSocket close code 4003**: Show "Permission denied" error on `SCR-018`.
- **Network loss on post-auth screens**: Show cached data if available, retry on reconnect.

## Timestamp Display
All timestamps from backend are ISO-8601 with +08:00 offset (Asia/Manila). Display formatted for readability (e.g., "Feb 12, 2026 07:00 AM").
