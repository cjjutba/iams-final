# Faculty App Screen Flows

## Auth Flow (Pre-auth)
1. Faculty enters via `SCR-005` FacultyLoginScreen (pre-auth — no JWT required).
2. Optional password recovery through `SCR-006` ForgotPasswordScreen (pre-auth).
3. Successful auth stores tokens in SecureStore and routes to `SCR-019` FacultyHomeScreen (post-auth).

## Schedule and Live Class Flow (Post-auth)
1. `SCR-019` shows current-day class overview and active class status. JWT required for all API calls.
2. `SCR-020` displays full faculty schedule list via `GET /schedules/me`.
3. Selecting/entering active class opens `SCR-021` live attendance (connects WebSocket via `?token=<jwt>`).
4. Active class resolved using Asia/Manila timezone (+08:00).

## Class Operations Flow (Post-auth)
1. From `SCR-021`, open `SCR-022` class detail summary.
2. Drill into `SCR-023` student detail/presence logs.
3. Use `SCR-024` for manual attendance actions via `POST /attendance/manual`.
4. View alert list in `SCR-025` FacultyAlertsScreen.
5. View summary/report context in `SCR-026`.

## Profile and Notification Flow (Post-auth)
1. View profile in `SCR-027` via `GET /auth/me`.
2. Edit profile in `SCR-028` via `PATCH /users/{id}` and return to profile.
3. Open notification feed in `SCR-029` — connects WebSocket via `?token=<jwt>` for realtime events.

## Realtime Recovery Flow
1. Live/notification screen detects websocket disconnect.
2. UI enters reconnecting state.
3. Client retries connection with exponential backoff.
4. On close code 4001: clear session and redirect to login.
5. On close code 4003: show forbidden error message.
6. On 1011 or network loss: reconnect with backoff. Screen updates continue without app restart.

## Auth Error Handling
- Any 401 response → attempt refresh → if fails, redirect to SCR-005 (login).
- WebSocket close code 4001 → redirect to login.
- WebSocket close code 4003 → show error message.

## Timestamp Display
- All schedule times, attendance timestamps, and alert timestamps display in Asia/Manila timezone (+08:00).
