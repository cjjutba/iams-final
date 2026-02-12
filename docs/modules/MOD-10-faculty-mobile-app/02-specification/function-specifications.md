# Function Specifications

## FUN-10-01 Faculty Login and Session Restore
- **Type:** Auth flow
- **Auth:** Pre-auth (login, forgot-password) → Post-auth (refresh, me, session)

Goal:
- Authenticate faculty users and restore active session state across app restarts.

Inputs:
- Faculty credentials (email + password), auth API responses, local secure session data.

Process:
1. Submit faculty login credentials via `POST /auth/login` (pre-auth, no JWT required).
2. Receive response envelope: `{ "success": true, "data": { "access_token": "...", "refresh_token": "...", "user": { ... } } }`.
3. Store tokens in Expo SecureStore (never AsyncStorage).
4. Fetch current profile via `GET /auth/me` (post-auth, JWT required).
5. Persist session/token securely.
6. On app restart: hydrate auth state from SecureStore before protected navigation.
7. On token expiry: attempt refresh via `POST /auth/refresh` (post-auth). If refresh fails, clear session and redirect to login.

Outputs:
- Active authenticated faculty session.

Validation Rules:
- Reject invalid credentials with clear UI feedback.
- Enforce fallback to login when session refresh fails.
- Parse response envelope without assuming `details` array exists.

Error Format:
```json
{ "success": false, "error": { "code": "INVALID_CREDENTIALS", "message": "..." } }
```

---

## FUN-10-02 View Schedule and Active Class
- **Type:** Data view
- **Auth:** Post-auth (JWT required)

Goal:
- Present faculty teaching schedule and determine active class context.

Inputs:
- Authenticated faculty context, schedule API response, current time/day.

Process:
1. Fetch schedules via `GET /schedules/me` (post-auth).
2. Response fields use snake_case: `subject_name`, `start_time`, `end_time`, `room_name`, `day_of_week`.
3. Resolve active class based on schedule/time rules using Asia/Manila timezone (+08:00).
4. Route user to live class view when active class exists.

Outputs:
- Schedule list and active class indicator.

Validation Rules:
- Handle no-class/no-schedule states gracefully.
- Ensure only faculty-owned classes are shown.
- Display times in +08:00 timezone.

---

## FUN-10-03 Live Attendance Monitoring
- **Type:** Real-time view
- **Auth:** Post-auth (JWT required) + WebSocket (JWT via query param)

Goal:
- Provide realtime visibility of attendance during an active class.

Inputs:
- Live attendance endpoint data and websocket events.

Process:
1. Load live roster via `GET /attendance/live/{schedule_id}` (post-auth).
2. Connect to WebSocket: `WS /ws/{user_id}?token=<jwt>` (JWT via query param, not header).
3. Subscribe to `attendance_update` events. Event envelope: `{ "type": "attendance_update", "data": { ... } }`.
4. Update roster rows as status changes arrive.
5. Handle close codes: 4001 → login redirect, 4003 → error message, 1011 → backoff retry.

Outputs:
- Live attendance roster with current status signals.

Validation Rules:
- Display inactive-session state clearly.
- Parse event payloads safely and ignore malformed items.
- Show reconnecting indicator during network loss.

---

## FUN-10-04 Manual Attendance Updates
- **Type:** Form submission
- **Auth:** Post-auth (JWT required)

Goal:
- Allow faculty to manually insert/update attendance entries when needed.

Inputs:
- Student, schedule, date, status, remarks payload.

Process:
1. Validate manual entry fields (student_id, schedule_id, date as YYYY-MM-DD, status enum, optional remarks).
2. Submit via `POST /attendance/manual` (post-auth).
3. Response: `{ "success": true, "data": { ... }, "message": "Attendance updated" }`.
4. Refresh live/today views with updated values.

Outputs:
- Manual update acknowledgment and reflected roster changes.

Validation Rules:
- Restrict action to faculty role.
- Ensure status value uses allowed enum: `present`, `late`, `absent`, `early_leave`.
- Handle 403 and validation errors with actionable feedback.

---

## FUN-10-05 Early-Leave Alerts and Class Summaries
- **Type:** Alert/summary view
- **Auth:** Post-auth (JWT required) + WebSocket events

Goal:
- Show early-leave warnings during session and summary outcomes after session.

Inputs:
- Presence endpoint responses, websocket alerts, session-end summary events.

Process:
1. Fetch early-leave list via `GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` (post-auth).
2. Render alert feed in faculty alert screens.
3. Listen for `early_leave` and `session_end` WebSocket events.
4. Fetch summary via `GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` (post-auth).
5. Render summary totals after class/session completion.

Outputs:
- Alert visibility and class summary views.

Validation Rules:
- Alert list must filter by selected class/date context.
- Summary values must align with attendance totals.
- Display timestamps in +08:00 timezone.

---

## FUN-10-06 Faculty Profile and Notifications
- **Type:** Profile management + real-time feed
- **Auth:** Post-auth (JWT required) + WebSocket (JWT via query param)

Goal:
- Provide faculty profile management and notification feed experience.

Inputs:
- Profile APIs, websocket events, local notification state.

Process:
1. Load faculty profile via `GET /auth/me` (post-auth).
2. Submit profile edits via `PATCH /users/{id}` (post-auth).
3. Use `authService.updateProfile(userId, data)` — userId as first argument.
4. Use `authService.changePassword(oldPassword, newPassword)` — two string arguments, not object.
5. Connect to WebSocket: `WS /ws/{user_id}?token=<jwt>`.
6. Stream and display notification events with event envelope: `{ "type": "...", "data": { ... } }`.
7. Handle close codes: 4001 → login redirect, 4003 → forbidden message.

Outputs:
- Updated profile and live faculty notification feed.

Validation Rules:
- Profile edits respect backend field constraints.
- Notification screen supports reconnect behavior with exponential backoff.
- Parse response envelope without assuming `details` array.
