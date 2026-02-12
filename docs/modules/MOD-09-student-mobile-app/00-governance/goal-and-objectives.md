# Goal and Objectives

## Module Goal
Deliver a complete student mobile experience from onboarding through attendance visibility, profile management, and notifications.

## Auth Context
MOD-09 contains both pre-auth flows (onboarding, login, registration) and post-auth flows (dashboard, profile, notifications). The registration flow bridges the two: identity verification and account setup are pre-auth, while face registration uses the newly created account credentials.

## Problem Statement
Students need a reliable, guided, and secure mobile flow for account setup, face registration, and continuous access to attendance information.

## Stakeholders
| Stakeholder | Interest | Module Reference |
|---|---|---|
| Student users | Self-registration, attendance visibility, notifications | MOD-09 (this module) |
| Backend auth service | JWT issuance, token refresh, student ID verification | MOD-01 |
| Face recognition service | Face image upload, embedding generation | MOD-03 |
| Schedule/enrollment service | Class schedules, enrollment data | MOD-05 |
| Attendance service | Attendance records, history, today view | MOD-06 |
| WebSocket service | Real-time notification delivery | MOD-08 |
| Faculty users | Indirect — student data quality affects faculty views | MOD-10 |

## Objectives
1. Implement onboarding and role-entry experience for student users.
2. Provide stable student authentication and session persistence using backend-issued JWT.
3. Enforce a 4-step student registration workflow with validation gates (pre-auth to post-auth transition).
4. Provide attendance dashboard, schedule, history, and detail views with timezone-aware timestamp display.
5. Provide profile editing and face re-registration paths.
6. Provide realtime student notifications via WebSocket integration (JWT via `token` query param).

## MVP Success Signals
- Student can complete onboarding to authenticated home flow.
- Student registration blocks invalid progression at each step.
- Pre-auth endpoints (`verify-student-id`, `register`, `login`) work without JWT.
- Post-auth endpoints (`/schedules/me`, `/attendance/me`, etc.) require valid JWT.
- Attendance and schedule data render correctly with loading/empty/error states.
- All timestamps display in Asia/Manila timezone (+08:00).
- Student can view notifications without app restart after reconnect.

## Non-Goals for MOD-09
- Faculty-only features and workflows.
- Admin portal screens.
- Advanced analytics and custom reports.
- Push notification provider integration (FCM/APNs).
