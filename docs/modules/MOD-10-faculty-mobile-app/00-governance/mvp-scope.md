# MVP Scope

## In Scope
| Function | Auth Type |
|---|---|
| `FUN-10-01`: Faculty login and session restore | Pre-auth (login) → Post-auth (session) |
| `FUN-10-02`: View schedule and active class | Post-auth (JWT required) |
| `FUN-10-03`: Live attendance monitoring | Post-auth (JWT required) + WebSocket (JWT via query param) |
| `FUN-10-04`: Manual attendance updates | Post-auth (JWT required) |
| `FUN-10-05`: View early-leave alerts and class summaries | Post-auth (JWT required) + WebSocket events |
| `FUN-10-06`: Faculty profile and notifications | Post-auth (JWT required) + WebSocket (JWT via query param) |

## Screen Scope
- Pre-auth: `SCR-005` (FacultyLoginScreen), `SCR-006` (ForgotPasswordScreen)
- Post-auth: `SCR-019` to `SCR-029` (all faculty portal screens)

## Token Architecture
- **Backend-issued JWT** — mobile does NOT use Supabase JS client SDK directly.
- Tokens stored in **Expo SecureStore** (never AsyncStorage for tokens).
- **Axios interceptors** auto-attach `Authorization: Bearer <token>` on post-auth requests.
- On 401 response: attempt token refresh via `POST /auth/refresh`, then retry. If refresh fails, redirect to login.
- WebSocket uses JWT via `token` query parameter: `WS /ws/{user_id}?token=<jwt>`.

## Timezone Rules
- All timestamps in ISO-8601 with `+08:00` offset (Asia/Manila).
- Date filters use `YYYY-MM-DD` format.
- `TIMEZONE` environment variable available for display logic.

## Design System Constraints
- Text `weight` prop: only `'400' | '500' | '600' | '700'` (not bold/semibold/medium/regular).
- Avatar component: no `style` prop — wrap in `<View style={...}>` instead.
- Divider `spacing`: SpacingKey = `0|1|2|3|4|5|6|8|10|12|16|20|24` (numbers, not strings).
- `colors.status` only has: `present`, `late`, `absent`, `early_leave` (not error/warning/success).
- Use top-level `colors.error`, `colors.warning`, `colors.success` for non-status colors.
- API response fields use **snake_case** (`subject_name`, `start_time`, `room_name`).

## Out of Scope
- Faculty self-registration or invite code flows.
- Full admin reporting suite beyond module screens.
- Push-provider integration outside websocket path.

## Scope Dependencies
- Auth contracts from `MOD-01`.
- Profile endpoints from `MOD-02`.
- Schedule data from `MOD-05`.
- Attendance and manual entry from `MOD-06`.
- Early-leave data from `MOD-07`.
- Realtime transport from `MOD-08`.

## Gate Criteria
- [ ] Faculty login works with pre-seeded credentials (pre-auth).
- [ ] All post-auth endpoints reject without JWT (401).
- [ ] WebSocket connects with `?token=<jwt>` and returns close codes on auth failure.
- [ ] Response envelope parsed correctly (no `details` array assumed).
- [ ] Timestamps display in +08:00 timezone.
- [ ] Design system constraints followed in all screens.
- [ ] All T10 tests pass.
- [ ] Traceability matrix fully mapped.
