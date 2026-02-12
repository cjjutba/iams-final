# Working Rules

## Source-of-Truth Rules
1. Canonical sources: `architecture.md`, `implementation.md`, `database-schema.md`, `api-reference.md`, `prd.md`.
2. If MOD-10 docs conflict with main docs, main docs win.
3. If API contract or screen scope changes, update docs before code.

## Implementation Rules
1. Implement only `FUN-10-01` to `FUN-10-06` for Module 10 tasks.
2. Faculty account creation is not part of this module in MVP.
3. Faculty login must use pre-seeded account assumptions.
4. Live attendance screens must reflect backend realtime updates.
5. Manual attendance actions must follow backend validation and role rules.
6. Faculty UI must include loading/empty/error states for all API-driven screens.
7. Do not expose student-only registration screens in faculty route flows.

## Auth Rules
1. Faculty login (`POST /auth/login`) is the only pre-auth API call. No JWT required.
2. Forgot password (`POST /auth/forgot-password`) is pre-auth. No JWT required.
3. All other endpoints require `Authorization: Bearer <token>` header.
4. Tokens are backend-issued JWT — do NOT use Supabase JS client SDK.
5. Store tokens in Expo SecureStore (never AsyncStorage).
6. Axios interceptors auto-attach Bearer token on all post-auth requests.
7. On 401: attempt refresh via `POST /auth/refresh`. If refresh fails, clear session and redirect to login.
8. WebSocket connects via `WS /ws/{user_id}?token=<jwt>` (JWT in query param, not header).

## Timezone Rules
1. All timestamps display in Asia/Manila timezone (ISO-8601 with `+08:00` offset).
2. Date filter parameters use `YYYY-MM-DD` format.
3. Never assume UTC-only — always apply timezone offset for display.

## Design System Rules
1. Follow Text weight, Avatar, Divider, and colors.status constraints from `mvp-scope.md`.
2. Access API response fields via snake_case names.
3. Do not invent color tokens — use only what the design system provides.

## Notification Rules
1. WebSocket requires JWT via `token` query param after auth readiness.
2. Handle close code 4001 → redirect to login.
3. Handle close code 4003 → show forbidden error message.
4. Reconnect with exponential backoff on 1011 or network loss.

## Quality Rules
1. Notification and reconnect behavior must be resilient.
2. Every implementation commit should mention `MOD-10` and at least one `FUN-10-*`.
3. Parse HTTP response envelope without assuming `details` array exists.
