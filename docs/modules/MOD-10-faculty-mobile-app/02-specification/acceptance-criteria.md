# Acceptance Criteria

## Module-Level
- Faculty can login and restore session reliably using backend-issued JWT stored in SecureStore.
- Faculty can view schedule and monitor a live class end-to-end.
- Manual attendance actions are reflected in live/today views.
- Early-leave alerts and class summaries are visible in faculty screens.
- Profile and notifications flows are functional with reconnect handling.
- Pre-auth endpoints (`/auth/login`, `/auth/forgot-password`) work without JWT.
- All post-auth endpoints reject requests without valid JWT (401).
- WebSocket connects via `?token=<jwt>` and handles close codes 4001/4003.
- All timestamps display in Asia/Manila timezone (+08:00).
- HTTP response envelope parsed without assuming `details` array.
- Design system constraints followed in all screens.

## Function-Level

### FUN-10-01
- Valid faculty credentials establish session and route to faculty home.
- Login request sent to `POST /auth/login` (pre-auth, no JWT).
- Tokens stored in Expo SecureStore after successful login.
- Session restore works after app restart by hydrating from SecureStore.
- Token refresh failure clears session and redirects to login.
- Response envelope parsed correctly (no `details` array).

### FUN-10-02
- Faculty schedule renders correctly with active class indicator.
- Schedule fetched via `GET /schedules/me` (post-auth, JWT required).
- Active class resolved using Asia/Manila timezone.
- Empty schedule state is handled gracefully.

### FUN-10-03
- Live roster updates during active class via WebSocket events.
- WebSocket connected via `WS /ws/{user_id}?token=<jwt>` (JWT in query param).
- Event envelope parsed: `{ "type": "attendance_update", "data": { ... } }`.
- Close code 4001 triggers login redirect; 4003 shows error.
- Inactive class state is clear and non-blocking.
- Reconnecting indicator shown during network loss.

### FUN-10-04
- Manual attendance updates succeed for valid payloads.
- Submitted via `POST /attendance/manual` (post-auth).
- Status enum validated: `present`, `late`, `absent`, `early_leave`.
- Invalid status/fields show clear validation feedback.
- Success response refreshes live/today views.

### FUN-10-05
- Early-leave alerts render for selected class/date.
- Fetched via `GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` (post-auth).
- Session summary view reflects backend totals.
- Timestamps in +08:00 timezone.

### FUN-10-06
- Profile update succeeds and refreshes view state.
- Uses `authService.updateProfile(userId, data)` — userId as first arg.
- Uses `authService.changePassword(oldPassword, newPassword)` — two string args.
- Notifications stream updates via WebSocket with event envelope.
- Recovers after reconnect with exponential backoff.
- Close code 4001 → login redirect; 4003 → error message.
