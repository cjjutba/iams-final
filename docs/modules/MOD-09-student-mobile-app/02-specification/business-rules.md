# Business Rules

## Auth Rules
1. Student flow uses only student-allowed APIs and data (role = `student`).
2. Pre-auth endpoints (`/auth/verify-student-id`, `/auth/register`, `/auth/login`) require no JWT.
3. Post-auth endpoints require `Authorization: Bearer <token>` header.
4. WebSocket endpoint requires JWT via `token` query parameter (not Authorization header).
5. On 401 response: attempt `/auth/refresh`, fallback to login screen.
6. Mobile does NOT use Supabase JS client SDK — all auth flows go through backend REST API.
7. Student mobile must not expose faculty/admin-only controls or endpoints.

## Registration Rules
1. Registration requires successful ID verification against `student_records` table before account creation.
2. Duplicate registration (same student_id) is rejected by backend.
3. Registration requires valid face upload (3-5 images) before final submission.
4. Registration Steps 1-2 are pre-auth; Steps 3-4 are post-auth (using JWT from Step 2 registration response).
5. Step progression is strictly gated — no step skipping allowed.
6. Registration draft data persists locally during session, cleared on submit or cancel.

## Session and Storage Rules
1. Session tokens stored only in Expo SecureStore (never AsyncStorage or plaintext).
2. Sensitive fields (passwords, tokens) are never written to console logs.
3. Clear all secure and cached entries on logout.
4. Authenticated screens require active session or explicit re-auth flow.

## Data Display Rules
1. Data-driven screens implement the UI state triad: loading, empty, error.
2. All timestamps displayed in Asia/Manila timezone (+08:00) format.
3. Date filter parameters use `YYYY-MM-DD` format.
4. API response fields use snake_case (e.g., `subject_name`, `start_time`).

## Notification Rules
1. Notification UI tolerates transient WebSocket failures gracefully.
2. Show connection status indicator when disconnected/reconnecting.
3. Ignore unknown event types without crashing.
4. WebSocket close code 4001 → redirect to login screen.
5. WebSocket close code 4003 → show permission error message.

## Error Handling Rules
1. HTTP error response format: `{ "success": false, "error": { "code": "...", "message": "..." } }` — no `details` array.
2. WebSocket event envelope format: `{ "type": "...", "data": { ... } }` — distinct from HTTP envelope.
3. Show user-friendly error messages from backend `error.message` field.
4. Validation errors (400) → show field-level errors, preserve form state.

## Contract Rules
1. Contract changes across APIs require docs-first updates.
2. Any consumed contract change must be reflected in `03-api/` docs before code updates.

## Design System Rules
1. Follow monochrome UA-inspired design system constraints documented in `mvp-scope.md`.
2. Use only documented component props — do not extend with unsupported props.
