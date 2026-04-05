# Mobile API Integration Memory

## Critical: Backend Response Format
- Backend returns Pydantic response_model data **directly** -- there is NO generic `ApiResponse<T>` wrapper
- The frontend `ApiResponse` type exists in `types/auth.types.ts` but the backend never uses it
- Services must **not** unwrap `response.data.data` -- just use `response.data`
- See [endpoint-mapping.md](./endpoint-mapping.md) for full mapping

## Backend API Prefix
- All routes: `/api/v1/{router_prefix}/{endpoint}`
- Configured in `backend/app/config.py` as `API_PREFIX = "/api/v1"`
- Mobile `api.ts` base URL includes `/api/v1` already

## Auth Endpoint Mismatches (Fixed)
- Login: backend expects `{ identifier, password }` as JSON (not `email` or form-urlencoded)
- Register response: `{ success, message, user, tokens: { access_token, refresh_token, ... } }`
- GET /auth/me returns `UserResponse` directly (not wrapped)
- Change-password: `{ old_password, new_password }` (backend `PasswordChange` schema)
- Logout: POST /auth/logout exists, requires auth, returns `{ success, message }`
- Profile update: No endpoint on auth router; use PATCH `/users/{user_id}` instead

## Type Mismatches Between Frontend and Backend
- `VerifyStudentIdResponse`: Frontend has `{ success, data: { valid, ... } }` but backend returns `{ valid, student_info, message }` -- service transforms
- `AttendanceSummary`: Frontend uses `total/present/late/absent/early_leave` but backend uses `total_classes/present_count/late_count/absent_count/early_leave_count` -- service transforms
- `PresenceLog`: Backend `id` is `int`, frontend expects `string`; backend omits `attendance_id`/`created_at`
- `LoginRequest` type uses `email` field but backend `LoginRequest` uses `identifier`

## Attendance Endpoints
- GET /attendance/today returns `List[]` not single record (faculty only)
- GET /attendance/me/summary (not /attendance/summary)
- No /attendance/history endpoint exists
- No /attendance/export endpoint exists
- Early leaves: GET /attendance/early-leaves/ (with trailing slash)

## Face Endpoints
- Delete: `DELETE /face/{user_id}` (not `/face/registration`)
- Register/reregister: multipart with field name `images` (List[UploadFile])
- FormData for RN uses `{ uri, type, name }` objects cast as Blob

## WebSocket
- Backend sends `{ "event": "...", "data": {...} }` format
- Frontend `WebSocketMessage` type uses `event` field -- matches backend
- Linter auto-enhanced websocketService.ts with AppState listener, heartbeat, exponential backoff with jitter
- Connection states: DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING

## Notifications Router
- Exists at `backend/app/routers/notifications.py` but NOT registered in `main.py`
- Endpoints: GET /, PATCH /{id}/read, POST /read-all, GET /unread-count
- Created `notificationService.ts` anticipating registration

## Token Refresh Architecture
- `api.ts` uses request queue pattern for concurrent 401s
- Fresh axios instance used for refresh call (avoids interceptor loop)
- Queue processes all waiting requests on refresh success/failure
- `isRefreshing` flag prevents concurrent refresh attempts

## Android Token Management (Stream J, 2026-03-30)
- TokenManager: volatile cache + async DataStore init (no runBlocking)
- TokenAuthenticator: Mutex serializes concurrent 401 refresh attempts
- See [token-management.md](./token-management.md)

## Android WebSocket Client (Stream J, 2026-03-30)
- Constructor changed: now takes shared OkHttpClient + tokenProvider lambda
- FacultyLiveFeedViewModel needs updating to match new constructor
- See [websocket-notes.md](./websocket-notes.md)
