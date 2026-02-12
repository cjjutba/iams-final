# Working Rules

## Source-of-Truth Rules
1. Canonical sources: `architecture.md`, `api-reference.md`, `implementation.md`, `database-schema.md`, `prd.md`.
2. If module docs conflict with canonical sources, canonical sources win.
3. Screen IDs and names follow `docs/main/prd.md` screen list.

## Implementation Rules
1. Implement only `FUN-09-01` to `FUN-09-06` for Module 9 tasks.
2. Student mobile screens must follow IDs and scope in `05-screens/`.
3. Do not add unlisted screens or flows without updating docs first.
4. Registration step progression must be validation-gated (no step skipping).
5. Empty/loading/error states are required on all API-driven screens.
6. If API contract changes are needed, update docs before implementation.
7. Every implementation commit should mention `MOD-09` and at least one `FUN-09-*`.

## Auth Rules
1. Pre-auth endpoints (`/auth/verify-student-id`, `/auth/register`, `/auth/login`): no JWT required.
2. Post-auth endpoints (all others): require `Authorization: Bearer <token>` header.
3. WebSocket endpoint: JWT passed as `token` query parameter (not Authorization header).
4. On 401 response from any post-auth endpoint: attempt `/auth/refresh` first, then fallback to login screen.
5. Session tokens stored in Expo SecureStore only — never in AsyncStorage or plaintext logs.
6. Sensitive fields (passwords, tokens) are never written to console logs.
7. Mobile does NOT use Supabase JS client SDK directly — all auth goes through backend REST API.
8. Registration Steps 1-2 are pre-auth; Steps 3-4 transition to post-auth after account creation.

## Timezone Rules
1. Backend timestamps arrive in ISO-8601 with +08:00 offset (Asia/Manila).
2. Display timestamps formatted for user readability (e.g., "Feb 12, 2026 07:00 AM").
3. Date filter parameters use `YYYY-MM-DD` format.

## Design System Rules
1. Follow monochrome UA-inspired design system constraints (see `mvp-scope.md`).
2. Use only documented component props — do not extend with unsupported props.
3. Use snake_case for all API response field access (e.g., `subject_name`, not `subjectName`).

## Notification Rules
1. Realtime notifications must handle disconnect/reconnect safely.
2. Show connection status indicator when WebSocket is disconnected/reconnecting.
3. Parse event envelope safely and ignore unknown event types (no crash).
4. Feed must survive reconnect without app restart.

## Quality Rules
1. All API-driven screens implement the UI state triad: loading, empty, error.
2. Contract changes across APIs require docs-first updates.
3. No hardcoded backend URLs — use environment configuration.
