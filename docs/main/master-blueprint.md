# IAMS Master Blueprint (Single Source of Truth)

## 1. Goal
This document is the primary implementation contract for the IAMS MVP and thesis build.
Before coding any feature, read this file first, then open the linked detailed docs.

Module-level references are stored in `docs/modules/` (one file per `MOD-*`).

## 2. Working Rules
1. If a feature is not listed here, do not implement it.
2. Every implementation task must reference at least one module ID (`MOD-*`) and one function ID (`FUN-*`).
3. If code and docs conflict, update docs first, then code.
4. If two docs conflict, stop and create an ADR before implementation.
5. Every PR/commit should include traceability, for example: `Implements MOD-01 FUN-01-03`.

## 3. ID Conventions
- Module ID: `MOD-01`, `MOD-02`, ...
- Function ID: `FUN-01-01`, `FUN-01-02`, ...
- Screen ID: `SCR-001`, `SCR-002`, ...
- Table names: use exact DB table names from `docs/main/database-schema.md`.

## 4. MVP Scope Baseline
MVP includes:
- Student identity verification and registration
- Faculty login (pre-seeded accounts)
- Face registration and recognition
- Attendance marking
- Continuous presence tracking and early-leave detection
- Student mobile features (attendance viewing)
- Faculty mobile features (live attendance and alerts)
- Deployment for pilot testing

Out of MVP:
- Full admin dashboard
- Advanced analytics
- Multi-campus complex deployment

## 5. Module Catalog

| Module ID | Module Name | Primary Domain | Main Docs | Suggested AI Agents |
|---|---|---|---|---|
| MOD-01 | Authentication and Identity | Backend + Mobile | `docs/main/prd.md`, `docs/main/api-reference.md`, `docs/main/technical-specification.md` | `auth-security-specialist.md`, `backend-core-specialist.md`, `mobile-forms-validator.md` |
| MOD-02 | User and Profile Management | Backend + Mobile | `docs/main/api-reference.md`, `docs/main/database-schema.md` | `backend-core-specialist.md`, `mobile-frontend-specialist.md` |
| MOD-03 | Face Registration and Recognition | Backend + ML | `docs/main/implementation.md`, `docs/main/technical-specification.md`, `docs/main/api-reference.md` | `ml-face-recognition.md`, `backend-core-specialist.md` |
| MOD-04 | Edge Device Capture and Ingestion | Edge + Backend | `docs/main/implementation.md`, `docs/main/architecture.md`, `docs/main/technical-specification.md` | `edge-device-specialist.md`, `edge-api-specialist.md` |
| MOD-05 | Schedules and Enrollments | Backend | `docs/main/api-reference.md`, `docs/main/database-schema.md` | `business-logic-specialist.md`, `database-specialist.md` |
| MOD-06 | Attendance Records | Backend + Mobile | `docs/main/api-reference.md`, `docs/main/database-schema.md` | `backend-core-specialist.md`, `mobile-api-integration.md` |
| MOD-07 | Presence Tracking and Early Leave | Backend + ML | `docs/main/implementation.md`, `docs/main/technical-specification.md`, `docs/main/testing.md` | `tracking-presence-specialist.md`, `business-logic-specialist.md` |
| MOD-08 | Realtime Notifications and WebSocket | Backend + Mobile | `docs/main/api-reference.md`, `docs/main/technical-specification.md` | `websocket-specialist.md`, `websocket-mobile-specialist.md` |
| MOD-09 | Student Mobile App | Mobile | `docs/screens/screen-list.md`, `docs/main/prd.md`, `docs/main/implementation.md` | `mobile-frontend-specialist.md`, `mobile-state-manager.md`, `mobile-api-integration.md` |
| MOD-10 | Faculty Mobile App | Mobile | `docs/screens/screen-list.md`, `docs/main/prd.md` | `mobile-frontend-specialist.md`, `mobile-state-manager.md`, `mobile-api-integration.md` |
| MOD-11 | Data Import and Seed Operations | Scripts + Backend | `docs/main/prd.md`, `docs/main/deployment.md`, `docs/main/folder-structure.md` | `database-specialist.md`, `devops-deployment.md` |
| MOD-12 | Deployment and Runtime Operations | DevOps | `docs/main/deployment.md`, `docs/main/architecture.md` | `devops-deployment.md` |
| MOD-13 | Testing and Quality Validation | QA + All | `docs/main/testing.md`, `docs/main/best-practices.md` | `test-automation-specialist.md`, `docs-writer.md` |

## 6. Module Specifications

### MOD-01: Authentication and Identity
Purpose:
- Authenticate students and faculty and protect API access.

Functions:
- `FUN-01-01`: Verify student identity by student ID.
- `FUN-01-02`: Register student account after successful identity verification.
- `FUN-01-03`: Login with credentials and issue JWT/access tokens.
- `FUN-01-04`: Refresh access token.
- `FUN-01-05`: Return current authenticated user profile.

API Contracts:
- `POST /auth/verify-student-id`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

Data:
- `users`
- University validation data source (CSV/JRMSU import)

Screens:
- `SCR-004` StudentLoginScreen
- `SCR-005` FacultyLoginScreen
- `SCR-006` ForgotPasswordScreen
- `SCR-007` StudentRegisterStep1Screen
- `SCR-008` StudentRegisterStep2Screen
- `SCR-010` StudentRegisterReviewScreen

Done Criteria:
- Token lifecycle works (issue, verify, refresh, reject expired).
- Student registration cannot proceed without verified identity.
- Faculty self-registration is blocked in MVP.
- Auth errors follow documented format.

### MOD-02: User and Profile Management
Purpose:
- Manage user records and profile updates.

Functions:
- `FUN-02-01`: List users (admin scope).
- `FUN-02-02`: Get user by ID.
- `FUN-02-03`: Update user profile fields.
- `FUN-02-04`: Delete/deactivate user.

API Contracts:
- `GET /users?role=student&page=1&limit=20`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`

Data:
- `users`
- `face_registrations` (cascade impact on delete/deactivate)

Screens:
- `SCR-015` StudentProfileScreen
- `SCR-016` StudentEditProfileScreen
- `SCR-027` FacultyProfileScreen
- `SCR-028` FacultyEditProfileScreen

Done Criteria:
- Role-based access enforced.
- Profile edits validated and persisted.
- Delete/deactivate behavior documented and safe.

### MOD-03: Face Registration and Recognition
Purpose:
- Register student face embeddings and identify faces during class.

Functions:
- `FUN-03-01`: Upload and validate 3-5 face images.
- `FUN-03-02`: Generate embeddings.
- `FUN-03-03`: Store and sync embeddings with FAISS.
- `FUN-03-04`: Recognize faces using similarity threshold.
- `FUN-03-05`: Check whether user already has registered face.

API Contracts:
- `POST /face/register`
- `POST /face/recognize`
- `GET /face/status`

Data:
- `face_registrations`
- `users`
- Local FAISS index file

Screens:
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
- `SCR-030` CameraScreen

Done Criteria:
- Reject invalid images (blur, no face, multiple faces, too small).
- Embeddings remain consistent between DB and FAISS.
- Recognition threshold is configurable.

### MOD-04: Edge Device Capture and Ingestion
Purpose:
- Capture classroom frames, detect faces, and send face crops to backend.

Functions:
- `FUN-04-01`: Capture frames from camera.
- `FUN-04-02`: Detect and crop faces.
- `FUN-04-03`: Compress and send crops to backend.
- `FUN-04-04`: Queue unsent data when backend is unreachable.
- `FUN-04-05`: Retry with bounded queue policy.

API Contracts:
- `POST /face/process`

Data:
- Local edge queue (in-memory bounded queue)
- Optional local logs

Screens:
- None (edge runtime module)

Done Criteria:
- Queue max size and TTL policy enforced.
- Retry behavior does not block frame capture loop.
- Errors and queue depth are logged.

### MOD-05: Schedules and Enrollments
Purpose:
- Define class schedules and enroll students per class.

Functions:
- `FUN-05-01`: List schedules by filters/day.
- `FUN-05-02`: Get schedule by ID.
- `FUN-05-03`: Create schedule (admin).
- `FUN-05-04`: Get schedules for current user.
- `FUN-05-05`: Get students assigned to schedule.

API Contracts:
- `GET /schedules?day=1`
- `GET /schedules/{id}`
- `POST /schedules`
- `GET /schedules/me`
- `GET /schedules/{id}/students`

Data:
- `rooms`
- `schedules`
- `enrollments`
- `users`

Screens:
- `SCR-012` StudentScheduleScreen
- `SCR-020` FacultyScheduleScreen

Done Criteria:
- Time/day filters return correct active schedules.
- Enrollment relationships are enforced.
- Schedule ownership and permissions are validated.

### MOD-06: Attendance Records
Purpose:
- Record attendance events and expose history/live class data.

Functions:
- `FUN-06-01`: Mark attendance from recognition events.
- `FUN-06-02`: Return today's attendance for a class.
- `FUN-06-03`: Return student personal attendance history.
- `FUN-06-04`: Return filtered attendance records.
- `FUN-06-05`: Allow manual attendance entry by faculty.
- `FUN-06-06`: Return live attendance roster for active class.

API Contracts:
- `GET /attendance/today?schedule_id=uuid`
- `GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `POST /attendance/manual`
- `GET /attendance/live/{schedule_id}`

Data:
- `attendance_records`
- `schedules`
- `users`

Screens:
- `SCR-011` StudentHomeScreen
- `SCR-013` StudentAttendanceHistoryScreen
- `SCR-014` StudentAttendanceDetailScreen
- `SCR-019` FacultyHomeScreen
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-024` FacultyManualEntryScreen

Done Criteria:
- Duplicate attendance marking for same student/session is prevented.
- Manual override is auditable.
- History queries support date filters.

### MOD-07: Presence Tracking and Early Leave
Purpose:
- Continuously monitor in-session presence and detect early leaves.

Functions:
- `FUN-07-01`: Start and manage session state per schedule/date.
- `FUN-07-02`: Run periodic scan (default 60s cycle).
- `FUN-07-03`: Maintain miss counters per student.
- `FUN-07-04`: Flag early leave at threshold.
- `FUN-07-05`: Compute presence score.
- `FUN-07-06`: Return presence logs and early-leave events.

API Contracts:
- `GET /presence/{attendance_id}/logs`
- `GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD`

Data:
- `presence_logs`
- `early_leave_events`
- `attendance_records`
- `schedules`
- `enrollments`

Screens:
- `SCR-022` FacultyClassDetailScreen
- `SCR-023` FacultyStudentDetailScreen
- `SCR-025` FacultyEarlyLeaveAlertsScreen

Done Criteria:
- Session semantics are tied to schedule and date.
- Miss threshold is configurable and documented.
- Early-leave detection is test-covered.

### MOD-08: Realtime Notifications and WebSocket
Purpose:
- Push attendance and early-leave updates to mobile clients in realtime.

Functions:
- `FUN-08-01`: Open authenticated WebSocket connections.
- `FUN-08-02`: Publish attendance update events.
- `FUN-08-03`: Publish early-leave events.
- `FUN-08-04`: Publish session-end summary events.
- `FUN-08-05`: Handle reconnect and stale connection cleanup.

API Contracts:
- `WS /ws/{user_id}`

Events:
- `attendance_update`
- `early_leave`
- `session_end`

Data:
- Ephemeral connection map
- Optional message delivery logs

Screens:
- `SCR-018` StudentNotificationsScreen
- `SCR-029` FacultyNotificationsScreen
- `SCR-021` FacultyLiveAttendanceScreen

Done Criteria:
- Event payloads match API docs.
- Reconnect behavior is stable on network interruptions.
- Notification screens update without app restart.

### MOD-09: Student Mobile App
Purpose:
- Provide student onboarding, registration, and attendance visibility.

Functions:
- `FUN-09-01`: Onboarding and welcome flow.
- `FUN-09-02`: Student login and token persistence.
- `FUN-09-03`: 4-step student registration flow.
- `FUN-09-04`: Attendance dashboard and history.
- `FUN-09-05`: Profile and face re-registration.
- `FUN-09-06`: Student notifications.

Screens:
- Shared: `SCR-001`, `SCR-002`, `SCR-003`
- Auth and registration: `SCR-004`, `SCR-006`, `SCR-007`, `SCR-008`, `SCR-009`, `SCR-010`
- Student portal: `SCR-011`, `SCR-012`, `SCR-013`, `SCR-014`, `SCR-015`, `SCR-016`, `SCR-017`, `SCR-018`

Done Criteria:
- Registration flow blocks progression on invalid data.
- All student API calls use authenticated session.
- Empty, loading, and error states are implemented.

### MOD-10: Faculty Mobile App
Purpose:
- Give faculty live visibility and control for class attendance.

Functions:
- `FUN-10-01`: Faculty login and session restore.
- `FUN-10-02`: View schedule and active class.
- `FUN-10-03`: Live attendance monitoring.
- `FUN-10-04`: Manual attendance updates.
- `FUN-10-05`: View early-leave alerts and class summaries.
- `FUN-10-06`: Faculty profile and notifications.

Screens:
- Auth: `SCR-005`, `SCR-006`
- Faculty portal: `SCR-019`, `SCR-020`, `SCR-021`, `SCR-022`, `SCR-023`, `SCR-024`, `SCR-025`, `SCR-026`, `SCR-027`, `SCR-028`, `SCR-029`

Done Criteria:
- Faculty can monitor a live class end-to-end.
- Manual entry updates are reflected in live/history views.
- Alert screens show realtime events.

### MOD-11: Data Import and Seed Operations
Purpose:
- Prepare baseline university data needed for MVP operation.

Functions:
- `FUN-11-01`: Import students CSV for identity validation.
- `FUN-11-02`: Seed faculty accounts.
- `FUN-11-03`: Import schedules.
- `FUN-11-04`: Import or map enrollments.

Data:
- `users`
- `schedules`
- `enrollments`
- External CSV datasets

Screens:
- None (operational scripts/module)

Done Criteria:
- Import scripts are repeatable and idempotent.
- Validation reports are generated for bad rows.
- Seeded faculty login is verified.

### MOD-12: Deployment and Runtime Operations
Purpose:
- Deploy backend, edge, and mobile with stable environment configs.

Functions:
- `FUN-12-01`: Configure environment files per runtime.
- `FUN-12-02`: Start backend, edge, and mobile services.
- `FUN-12-03`: Health checks and monitoring basics.
- `FUN-12-04`: Backup FAISS and database data.
- `FUN-12-05`: Rollback procedure for failed deployments.

Docs:
- `docs/main/deployment.md`
- `docs/main/architecture.md`

Done Criteria:
- Local pilot deployment works on same network.
- Cloud deployment path documented for future.
- Backup and rollback steps are tested.

### MOD-13: Testing and Quality Validation
Purpose:
- Verify functional correctness, integration, and thesis metrics.

Functions:
- `FUN-13-01`: Unit testing for services and utilities.
- `FUN-13-02`: Integration testing for API endpoints.
- `FUN-13-03`: End-to-end scenarios (registration, attendance, early leave).
- `FUN-13-04`: Validation against success metrics.
- `FUN-13-05`: Demo readiness checklist.

Docs:
- `docs/main/testing.md`
- `docs/main/best-practices.md`

Done Criteria:
- Test suite covers all MVP-critical flows.
- Failures are reproducible and tracked.
- Results support thesis evaluation metrics.

## 7. API Inventory (Canonical Endpoint List)

Auth:
- `POST /auth/verify-student-id`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

Users:
- `GET /users?role=student&page=1&limit=20`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}`

Face:
- `POST /face/register`
- `POST /face/recognize`
- `POST /face/process`
- `GET /face/status`

Schedules:
- `GET /schedules?day=1`
- `GET /schedules/{id}`
- `POST /schedules`
- `GET /schedules/me`
- `GET /schedules/{id}/students`

Attendance:
- `GET /attendance/today?schedule_id=uuid`
- `GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `POST /attendance/manual`
- `GET /attendance/live/{schedule_id}`

Presence:
- `GET /presence/{attendance_id}/logs`
- `GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD`

Realtime:
- `WS /ws/{user_id}`

## 8. Data Model Inventory (Canonical Table List)
- `users`
- `face_registrations`
- `rooms`
- `schedules`
- `enrollments`
- `attendance_records`
- `presence_logs`
- `early_leave_events`

## 9. Screen Inventory

### Shared Screens
| Screen ID | Screen Name |
|---|---|
| SCR-001 | SplashScreen |
| SCR-002 | OnboardingScreen |
| SCR-003 | WelcomeScreen |

### Auth Screens
| Screen ID | Screen Name |
|---|---|
| SCR-004 | StudentLoginScreen |
| SCR-005 | FacultyLoginScreen |
| SCR-006 | ForgotPasswordScreen |

### Student Registration Flow
| Screen ID | Screen Name |
|---|---|
| SCR-007 | StudentRegisterStep1Screen |
| SCR-008 | StudentRegisterStep2Screen |
| SCR-009 | StudentRegisterStep3Screen |
| SCR-010 | StudentRegisterReviewScreen |

### Student Portal
| Screen ID | Screen Name |
|---|---|
| SCR-011 | StudentHomeScreen |
| SCR-012 | StudentScheduleScreen |
| SCR-013 | StudentAttendanceHistoryScreen |
| SCR-014 | StudentAttendanceDetailScreen |
| SCR-015 | StudentProfileScreen |
| SCR-016 | StudentEditProfileScreen |
| SCR-017 | StudentFaceReregisterScreen |
| SCR-018 | StudentNotificationsScreen |

### Faculty Portal
| Screen ID | Screen Name |
|---|---|
| SCR-019 | FacultyHomeScreen |
| SCR-020 | FacultyScheduleScreen |
| SCR-021 | FacultyLiveAttendanceScreen |
| SCR-022 | FacultyClassDetailScreen |
| SCR-023 | FacultyStudentDetailScreen |
| SCR-024 | FacultyManualEntryScreen |
| SCR-025 | FacultyEarlyLeaveAlertsScreen |
| SCR-026 | FacultyReportsScreen |
| SCR-027 | FacultyProfileScreen |
| SCR-028 | FacultyEditProfileScreen |
| SCR-029 | FacultyNotificationsScreen |

### Utility Screens
| Screen ID | Screen Name |
|---|---|
| SCR-030 | CameraScreen |
| SCR-031 | SettingsScreen |
| SCR-032 | AboutScreen |
| SCR-033 | TermsScreen |
| SCR-034 | PrivacyScreen |
| SCR-035 | HelpScreen |

## 10. Module Dependency Order (Implementation Sequence)
1. `MOD-11` Data import and seed operations
2. `MOD-01` Authentication and identity
3. `MOD-02` User and profile management
4. `MOD-05` Schedules and enrollments
5. `MOD-03` Face registration and recognition
6. `MOD-04` Edge capture and ingestion
7. `MOD-06` Attendance records
8. `MOD-07` Presence tracking and early leave
9. `MOD-08` Realtime notifications and WebSocket
10. `MOD-09` Student mobile app
11. `MOD-10` Faculty mobile app
12. `MOD-12` Deployment and runtime operations
13. `MOD-13` Testing and quality validation

## 11. AI Task Prompt Template
Use this prompt format for Codex/Claude on every implementation task:

```text
Implement: MOD-XX / FUN-XX-YY

Read first:
- docs/main/master-blueprint.md
- <module-specific docs...>

Scope:
- Only implement listed function IDs.
- Do not add unlisted features.

Output required:
- Files changed
- Function IDs implemented
- Tests executed
- Risks or unresolved decisions
```

## 12. Change Control
- Any change to module scope, API contract, DB schema, or screen behavior must be updated in docs first.
- Record major design changes as ADR files (recommended path: `docs/main/adr/ADR-xxxx-title.md`).
- Keep this file updated whenever new module functions are added, removed, or deferred.
