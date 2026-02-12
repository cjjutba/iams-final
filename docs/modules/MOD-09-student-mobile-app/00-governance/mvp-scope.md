# MVP Scope

## In Scope
- `FUN-09-01`: Onboarding and welcome flow (pre-auth, local navigation only).
- `FUN-09-02`: Student login and token persistence (pre-auth → post-auth transition via `/auth/login`).
- `FUN-09-03`: Four-step registration flow:
  - Step 1 identity verification (pre-auth: `POST /auth/verify-student-id`)
  - Step 2 account setup (pre-auth: `POST /auth/register`)
  - Step 3 face registration (post-auth: `POST /face/register` with JWT)
  - Step 4 review and submit (post-auth: confirmation)
- `FUN-09-04`: Student home, schedule, attendance history/detail (post-auth, JWT required).
- `FUN-09-05`: Profile view/edit and face re-registration (post-auth, JWT required).
- `FUN-09-06`: Student notifications including realtime integration path (post-auth, WebSocket with JWT via `token` query param).

## Out of Scope
- Faculty mobile features (`MOD-10`).
- Admin operations.
- Offline-first full registration/auth.
- Push notification provider integration (FCM/APNs).
- Supabase client SDK direct auth (mobile uses backend REST API exclusively).

## Scope Dependencies
- Auth backend contracts from `MOD-01` (JWT issuance, refresh, verify-student-id).
- User management from `MOD-02` (profile PATCH endpoint).
- Face registration contracts from `MOD-03` (face upload, status check).
- Schedule and attendance data from `MOD-05` and `MOD-06`.
- Realtime transport contracts from `MOD-08` (WebSocket with JWT auth).

## Token Architecture
- Mobile app authenticates via `POST /auth/login` and receives backend-issued JWT.
- JWT is stored in Expo SecureStore (not plain AsyncStorage).
- All post-auth API calls include `Authorization: Bearer <token>` header.
- WebSocket connection passes JWT as `token` query parameter (not Authorization header).
- On 401 response: attempt `/auth/refresh`, fallback to login screen.
- Mobile does NOT use Supabase JS client SDK directly — all auth goes through backend API.

## Timezone Rules
- All timestamps from the backend use ISO-8601 with +08:00 offset (Asia/Manila).
- Mobile displays timestamps in local device timezone or formatted per Asia/Manila.
- Date filters use `YYYY-MM-DD` format aligned with backend expectations.

## Design System Constraints
- Text `weight` prop: only `'400' | '500' | '600' | '700'` (not bold/semibold/medium/regular).
- Avatar component: no `style` prop — wrap in `<View style={...}>` instead.
- Divider `spacing`: SpacingKey = `0|1|2|3|4|5|6|8|10|12|16|20|24` (numbers, not strings).
- `colors.status` only has: `present`, `late`, `absent`, `early_leave` (not error/warning/success).
- Use top-level `colors.error`, `colors.warning`, `colors.success` for non-status colors.
- No `colors.backgroundSecondary` — use `colors.secondary`.
- No `colors.overlay` — use `'rgba(0,0,0,0.5)'`.
- Schedule/Attendance API types use snake_case: `subject_name`, `start_time`, `room_name`.

## Gate Criteria
- [ ] All pre-auth endpoints callable without JWT.
- [ ] All post-auth endpoints return 401 without valid JWT.
- [ ] Registration flow blocks step skipping.
- [ ] Face registration requires 3-5 valid images.
- [ ] All data screens have loading/empty/error states.
- [ ] Timestamps display in correct timezone.
- [ ] WebSocket reconnects without app restart.
- [ ] Tokens stored in SecureStore, not plain text.
