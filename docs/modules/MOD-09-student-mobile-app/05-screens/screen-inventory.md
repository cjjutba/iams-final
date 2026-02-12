# Screen Inventory

## Shared Entry Screens (Pre-Auth)
| Screen ID | Screen Name | Auth | Module Function Mapping |
|---|---|---|---|
| SCR-001 | SplashScreen | Pre-auth | FUN-09-01 |
| SCR-002 | OnboardingScreen | Pre-auth | FUN-09-01 |
| SCR-003 | WelcomeScreen | Pre-auth | FUN-09-01 |

## Auth and Registration Screens (Pre-Auth → Post-Auth)
| Screen ID | Screen Name | Auth | Module Function Mapping |
|---|---|---|---|
| SCR-004 | StudentLoginScreen | Pre-auth | FUN-09-02 |
| SCR-006 | ForgotPasswordScreen | Pre-auth | FUN-09-02 |
| SCR-007 | StudentRegisterStep1Screen | Pre-auth | FUN-09-03 (Step 1) |
| SCR-008 | StudentRegisterStep2Screen | Pre-auth | FUN-09-03 (Step 2) |
| SCR-009 | StudentRegisterStep3Screen | Post-auth | FUN-09-03 (Step 3, JWT from registration) |
| SCR-010 | StudentRegisterReviewScreen | Post-auth | FUN-09-03 (Step 4) |

## Student Portal Screens (Post-Auth)
| Screen ID | Screen Name | Auth | Module Function Mapping |
|---|---|---|---|
| SCR-011 | StudentHomeScreen | Post-auth (JWT) | FUN-09-04 |
| SCR-012 | StudentScheduleScreen | Post-auth (JWT) | FUN-09-04 |
| SCR-013 | StudentAttendanceHistoryScreen | Post-auth (JWT) | FUN-09-04 |
| SCR-014 | StudentAttendanceDetailScreen | Post-auth (JWT) | FUN-09-04 |
| SCR-015 | StudentProfileScreen | Post-auth (JWT) | FUN-09-05 |
| SCR-016 | StudentEditProfileScreen | Post-auth (JWT) | FUN-09-05 |
| SCR-017 | StudentFaceReregisterScreen | Post-auth (JWT) | FUN-09-05 |
| SCR-018 | StudentNotificationsScreen | Post-auth (JWT via WS query param) | FUN-09-06 |

## Screen-to-API Mapping
| Screen | API Endpoints | Auth |
|---|---|---|
| SCR-004 | `POST /auth/login` | Pre-auth |
| SCR-006 | `POST /auth/forgot-password` | Pre-auth |
| SCR-007 | `POST /auth/verify-student-id` | Pre-auth |
| SCR-008 | `POST /auth/register` | Pre-auth |
| SCR-009 | `POST /face/register` | Post-auth (JWT) |
| SCR-011 | `GET /schedules/me`, `GET /attendance/today` | Post-auth (JWT) |
| SCR-012 | `GET /schedules/me` | Post-auth (JWT) |
| SCR-013 | `GET /attendance/me` | Post-auth (JWT) |
| SCR-014 | `GET /attendance/me` (detail) | Post-auth (JWT) |
| SCR-015 | `GET /auth/me` | Post-auth (JWT) |
| SCR-016 | `PATCH /users/{id}` | Post-auth (JWT) |
| SCR-017 | `GET /face/status`, `POST /face/register` | Post-auth (JWT) |
| SCR-018 | `WS /ws/{user_id}?token=<jwt>` | Post-auth (JWT via query param) |

## Auth Error Handling
- **401 on post-auth screens**: Attempt `/auth/refresh`, fallback to login screen (SCR-004).
- **WebSocket close code 4001**: Redirect to login screen.
- **WebSocket close code 4003**: Show permission error message on SCR-018.
