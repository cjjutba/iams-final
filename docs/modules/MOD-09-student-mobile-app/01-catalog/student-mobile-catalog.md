# Student Mobile Catalog

## Module Summary
- Module ID: `MOD-09`
- Module Name: Student Mobile App
- Primary Domain: Mobile

## Auth Context
MOD-09 functions span pre-auth (FUN-09-01, FUN-09-02, FUN-09-03 Steps 1-2) and post-auth (FUN-09-03 Steps 3-4, FUN-09-04, FUN-09-05, FUN-09-06). Mobile uses backend REST API for all auth — no Supabase JS client SDK.

## Function Catalog
| Function ID | Function Name | Auth Type | Brief Description |
|---|---|---|---|
| FUN-09-01 | Onboarding and welcome flow | Pre-auth (local) | Guide first-time users and route by role selection. |
| FUN-09-02 | Login and token persistence | Pre-auth → Post-auth | Authenticate students and restore sessions securely. |
| FUN-09-03 | 4-step registration flow | Pre-auth (Steps 1-2) / Post-auth (Steps 3-4) | Identity verification, account setup, face registration, review. |
| FUN-09-04 | Attendance dashboard and history | Post-auth (JWT required) | Show current status, schedule, and historical attendance. |
| FUN-09-05 | Profile and face re-registration | Post-auth (JWT required) | Manage profile fields and renew face data. |
| FUN-09-06 | Student notifications | Post-auth (WebSocket + JWT) | Show alerts and realtime updates in student notification UI. |

## Screen Domains
- Shared app entry (pre-auth): `SCR-001`, `SCR-002`, `SCR-003`
- Auth and registration (pre-auth → post-auth): `SCR-004`, `SCR-006`, `SCR-007`, `SCR-008`, `SCR-009`, `SCR-010`
- Student portal (post-auth): `SCR-011` to `SCR-018`

## API Domain
Module 9 consumes APIs from auth, user, face, schedules, attendance, and websocket modules. All API calls use backend REST endpoints — mobile does not call Supabase directly.

## Consumed API Summary
| API Group | Endpoints | Auth Required |
|---|---|---|
| Auth (pre-auth) | `/auth/verify-student-id`, `/auth/register`, `/auth/login` | No |
| Auth (post-auth) | `/auth/refresh`, `/auth/me` | Yes (JWT) |
| Attendance | `/schedules/me`, `/attendance/me`, `/attendance/today` | Yes (JWT) |
| Profile | `/users/{id}`, `PATCH /users/{id}` | Yes (JWT) |
| Face | `/face/status`, `/face/register` | Yes (JWT) |
| Notifications | `WS /ws/{user_id}?token=<jwt>` | Yes (JWT via query param) |
