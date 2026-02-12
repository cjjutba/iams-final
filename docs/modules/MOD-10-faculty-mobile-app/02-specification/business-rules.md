# Business Rules

## Auth Rules
1. Faculty accounts are pre-seeded in MVP — no self-registration.
2. Faculty login (`POST /auth/login`) is pre-auth — no JWT required.
3. Forgot password (`POST /auth/forgot-password`) is pre-auth — no JWT required.
4. All other API calls require `Authorization: Bearer <token>` header.
5. Tokens are backend-issued JWT — do not use Supabase JS client SDK.
6. On 401 response: attempt refresh, then redirect to login if refresh fails.
7. WebSocket requires JWT via `token` query parameter.

## Session and Storage Rules
1. Store access and refresh tokens in Expo SecureStore only.
2. Never store tokens in AsyncStorage.
3. Sensitive auth/session data must not be logged in plaintext.
4. Clear all secure and cached entries on logout.

## Data Display Rules
1. Faculty views must show only classes associated with authenticated faculty user.
2. All timestamps display in Asia/Manila timezone (ISO-8601 with +08:00 offset).
3. Date filter parameters use YYYY-MM-DD format.
4. Access API response fields via snake_case names.

## Attendance Rules
1. Live attendance screens depend on active class context.
2. Manual attendance updates must be auditable and role-restricted (faculty only).
3. Manual entry status must use allowed enum: `present`, `late`, `absent`, `early_leave`.
4. Early-leave visibility must follow schedule/date filtering.

## Notification Rules
1. WebSocket connects via `WS /ws/{user_id}?token=<jwt>` after faculty auth readiness.
2. Handle close code 4001 → redirect to login.
3. Handle close code 4003 → show forbidden error.
4. Reconnect with exponential backoff on 1011 or network loss.
5. Notifications must handle transient websocket disconnect safely.

## Error Handling Rules
1. Parse HTTP response envelope: `{ "success": bool, "data": {}, "error": { "code": "", "message": "" } }`.
2. Never assume a `details` array exists in error responses.
3. Handle 403 with permission message and block action.
4. Every API-driven faculty screen includes loading/empty/error states.

## Design System Rules
1. Follow Text weight, Avatar, Divider, and colors.status constraints from `mvp-scope.md`.
2. Do not invent color tokens — use only what the design system provides.

## Contract Rules
1. Upstream API changes require docs updates before code changes.
2. Profile editing must validate input before request submission.
