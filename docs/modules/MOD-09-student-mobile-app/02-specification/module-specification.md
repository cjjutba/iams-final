# Module Specification

## Module
- ID: `MOD-09`
- Name: Student Mobile App

## Purpose
Provide student onboarding, registration, and attendance visibility through a React Native mobile app that consumes backend REST APIs.

## Auth Context
- **Pre-auth functions**: FUN-09-01 (onboarding), FUN-09-02 (login), FUN-09-03 Steps 1-2 (verify ID, register)
- **Post-auth functions**: FUN-09-03 Steps 3-4 (face registration, review), FUN-09-04, FUN-09-05, FUN-09-06
- Mobile uses backend-issued JWT for all API calls — does not use Supabase JS client SDK directly.

## Functions
| Function ID | Name | Auth Type |
|---|---|---|
| FUN-09-01 | Onboarding and welcome flow | Pre-auth (local navigation) |
| FUN-09-02 | Student login and token persistence | Pre-auth → Post-auth |
| FUN-09-03 | 4-step student registration flow | Pre-auth (Steps 1-2) / Post-auth (Steps 3-4) |
| FUN-09-04 | Attendance dashboard and history | Post-auth (JWT required) |
| FUN-09-05 | Profile and face re-registration | Post-auth (JWT required) |
| FUN-09-06 | Student notifications | Post-auth (WebSocket + JWT via query param) |

## Screens
- Shared (pre-auth): `SCR-001`, `SCR-002`, `SCR-003`
- Auth and registration (pre-auth → post-auth): `SCR-004`, `SCR-006`, `SCR-007`, `SCR-008`, `SCR-009`, `SCR-010`
- Student portal (post-auth): `SCR-011`, `SCR-012`, `SCR-013`, `SCR-014`, `SCR-015`, `SCR-016`, `SCR-017`, `SCR-018`

## Cross-Module Dependencies
| Module | What MOD-09 Consumes | Auth Note |
|---|---|---|
| MOD-01 | JWT issuance, login, refresh, verify-student-id | Login/register are pre-auth; refresh/me are post-auth |
| MOD-02 | Profile PATCH endpoint | Post-auth |
| MOD-03 | Face registration and status | Post-auth |
| MOD-05 | Schedule list endpoint | Post-auth |
| MOD-06 | Attendance history and today endpoints | Post-auth |
| MOD-08 | WebSocket notification stream | Post-auth (JWT via `token` query param) |

## Done Criteria
- Registration flow blocks progression on invalid data.
- Pre-auth API calls work without JWT; post-auth calls require valid JWT.
- All student API calls use `Authorization: Bearer <token>` for post-auth endpoints.
- Empty, loading, and error states are implemented on all data-driven screens.
- Timestamps display in Asia/Manila timezone (+08:00).
- Tokens stored in Expo SecureStore only.
