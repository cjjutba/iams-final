# API Boundary Notes

## Ownership Boundaries
- `MOD-10` owns faculty mobile UX and local state behavior.
- Backend modules own endpoint contracts and business rules.

## Auth Boundary
- Mobile uses **backend-issued JWT** for all authentication — does NOT use Supabase JS client SDK.
- Tokens stored in **Expo SecureStore** (never AsyncStorage).
- **Axios interceptors** auto-attach `Authorization: Bearer <token>` on post-auth requests and handle 401 refresh.
- WebSocket uses JWT via `token` query parameter (not header).

## Pre-Auth vs Post-Auth API Table
| Endpoint | Method | Auth | Function | Notes |
|---|---|---|---|---|
| `/auth/login` | POST | Pre-auth | FUN-10-01 | Faculty email + password |
| `/auth/forgot-password` | POST | Pre-auth | FUN-10-01 | Password reset request |
| `/auth/refresh` | POST | Post-auth | FUN-10-01 | Token refresh |
| `/auth/me` | GET | Post-auth | FUN-10-01, FUN-10-06 | Current user context |
| `/schedules/me` | GET | Post-auth | FUN-10-02 | Faculty schedules |
| `/schedules/{id}/students` | GET | Post-auth | FUN-10-02, FUN-10-03 | Class roster |
| `/attendance/live/{schedule_id}` | GET | Post-auth | FUN-10-03 | Live roster |
| `/attendance/today` | GET | Post-auth | FUN-10-03, FUN-10-05 | Today records |
| `/attendance/manual` | POST | Post-auth | FUN-10-04 | Manual entry |
| `/attendance` | GET | Post-auth | FUN-10-05 | History/summary |
| `/presence/early-leaves` | GET | Post-auth | FUN-10-05 | Early-leave alerts |
| `/presence/{attendance_id}/logs` | GET | Post-auth | FUN-10-05 | Presence logs |
| `/users/{id}` | GET/PATCH | Post-auth | FUN-10-06 | Profile |
| `WS /ws/{user_id}?token=<jwt>` | WS | Post-auth (query param) | FUN-10-03, FUN-10-05, FUN-10-06 | Real-time events |

## Response Envelope Rules
**HTTP Success:** `{ "success": true, "data": { ... }, "message": "..." }`

**HTTP Error:** `{ "success": false, "error": { "code": "...", "message": "..." } }` — NO `details` array.

**WebSocket Event:** `{ "type": "...", "data": { ... } }` — distinct from HTTP envelope.

## Upstream Module Contracts
| Module | Contract | Auth Note |
|---|---|---|
| MOD-01 | Faculty auth/session endpoints | Pre-auth (login) / Post-auth (refresh, me) |
| MOD-02 | Profile endpoint operations | Post-auth |
| MOD-05 | Schedule and class roster data | Post-auth |
| MOD-06 | Live/today/manual attendance endpoints | Post-auth |
| MOD-07 | Early-leave and presence log endpoints | Post-auth |
| MOD-08 | WebSocket realtime transport | Post-auth (JWT via query param) |

## Contract Drift Policy
If any upstream contract changes:
1. Update `03-api/` docs in this module pack.
2. Update impacted screen-state docs in `05-screens/`.
3. Update `10-traceability/traceability-matrix.md` before merge.
