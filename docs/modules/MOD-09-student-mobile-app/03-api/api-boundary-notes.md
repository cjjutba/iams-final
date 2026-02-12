# API Boundary Notes

## Ownership Boundaries
- `MOD-09` owns student mobile UX, local state behavior, and API integration layer.
- Backend modules own endpoint contracts and business logic.
- Mobile does NOT own or modify backend responses — it consumes them as-is.

## Auth Boundary
- Mobile authenticates via `POST /auth/login` → receives backend-issued JWT.
- Mobile does NOT use Supabase JS client SDK — all auth goes through backend REST API.
- Pre-auth endpoints: `/auth/verify-student-id`, `/auth/register`, `/auth/login` — no JWT required.
- Post-auth endpoints: all others — require `Authorization: Bearer <token>` header.
- WebSocket: JWT passed as `token` query parameter (not Authorization header).
- On 401: attempt `/auth/refresh`, fallback to login screen.

## Pre-Auth vs Post-Auth API Table
| Endpoint | Auth Status | Used By |
|---|---|---|
| `POST /auth/verify-student-id` | Pre-auth (no JWT) | FUN-09-03 Step 1 |
| `POST /auth/register` | Pre-auth (no JWT) | FUN-09-03 Step 2 |
| `POST /auth/login` | Pre-auth (no JWT) | FUN-09-02 |
| `POST /auth/refresh` | Post-auth (JWT) | FUN-09-02 |
| `GET /auth/me` | Post-auth (JWT) | FUN-09-02, FUN-09-05 |
| `GET /schedules/me` | Post-auth (JWT) | FUN-09-04 |
| `GET /attendance/me` | Post-auth (JWT) | FUN-09-04 |
| `GET /attendance/today` | Post-auth (JWT) | FUN-09-04 |
| `GET /users/{id}` | Post-auth (JWT) | FUN-09-05 |
| `PATCH /users/{id}` | Post-auth (JWT) | FUN-09-05 |
| `GET /face/status` | Post-auth (JWT) | FUN-09-05 |
| `POST /face/register` | Post-auth (JWT) | FUN-09-03 Step 3, FUN-09-05 |
| `WS /ws/{user_id}` | Post-auth (JWT via query param) | FUN-09-06 |

## Upstream Module Contracts Used
| Module | Contract | Auth Note |
|---|---|---|
| MOD-01 | Auth and identity endpoints | Login/register pre-auth; refresh/me post-auth |
| MOD-02 | Profile update endpoint (`PATCH /users/{id}`) | Post-auth |
| MOD-03 | Face registration/status endpoints | Post-auth |
| MOD-05 | Student schedule endpoint | Post-auth |
| MOD-06 | Student attendance endpoints | Post-auth |
| MOD-08 | WebSocket event transport | Post-auth (JWT via query param) |

## Response Envelope Rules
- HTTP success: `{ "success": true, "data": { ... }, "message": "..." }`
- HTTP error: `{ "success": false, "error": { "code": "...", "message": "..." } }` — NO `details` array.
- WebSocket event: `{ "type": "...", "data": { ... } }` — distinct from HTTP envelope.

## Contract Drift Policy
If any upstream payload or auth requirement changes:
1. Update `03-api/` docs in this module.
2. Update impacted screen-state docs in `05-screens/`.
3. Update traceability matrix before implementation merge.
