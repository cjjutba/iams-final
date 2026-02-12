# Screen Inventory

## Auth Screens (Pre-auth)
| Screen ID | Screen Name | Auth | Function Mapping |
|---|---|---|---|
| SCR-005 | FacultyLoginScreen | Pre-auth | FUN-10-01 |
| SCR-006 | ForgotPasswordScreen | Pre-auth | FUN-10-01 |

## Faculty Portal Screens (Post-auth)
| Screen ID | Screen Name | Auth | Function Mapping |
|---|---|---|---|
| SCR-019 | FacultyHomeScreen | Post-auth | FUN-10-02 |
| SCR-020 | FacultyScheduleScreen | Post-auth | FUN-10-02 |
| SCR-021 | FacultyLiveAttendanceScreen | Post-auth | FUN-10-03 |
| SCR-022 | FacultyClassDetailScreen | Post-auth | FUN-10-05 |
| SCR-023 | FacultyStudentDetailScreen | Post-auth | FUN-10-03, FUN-10-05 |
| SCR-024 | FacultyManualEntryScreen | Post-auth | FUN-10-04 |
| SCR-025 | FacultyAlertsScreen | Post-auth | FUN-10-05 |
| SCR-026 | FacultyReportsScreen | Post-auth | FUN-10-05 |
| SCR-027 | FacultyProfileScreen | Post-auth | FUN-10-06 |
| SCR-028 | FacultyEditProfileScreen | Post-auth | FUN-10-06 |
| SCR-029 | FacultyNotificationsScreen | Post-auth | FUN-10-06 |

## Screen-to-API Mapping
| Screen | API Endpoints | Auth |
|---|---|---|
| SCR-005 | `POST /auth/login` | Pre-auth |
| SCR-006 | `POST /auth/forgot-password` | Pre-auth |
| SCR-019 | `GET /schedules/me`, `GET /auth/me` | Post-auth |
| SCR-020 | `GET /schedules/me` | Post-auth |
| SCR-021 | `GET /attendance/live/{schedule_id}`, `WS /ws/{user_id}?token=<jwt>` | Post-auth |
| SCR-022 | `GET /attendance/today`, `GET /presence/early-leaves` | Post-auth |
| SCR-023 | `GET /presence/{attendance_id}/logs` | Post-auth |
| SCR-024 | `POST /attendance/manual` | Post-auth |
| SCR-025 | `GET /presence/early-leaves` | Post-auth |
| SCR-026 | `GET /attendance?schedule_id=...&start_date=...&end_date=...` | Post-auth |
| SCR-027 | `GET /auth/me` | Post-auth |
| SCR-028 | `PATCH /users/{id}` | Post-auth |
| SCR-029 | `WS /ws/{user_id}?token=<jwt>` | Post-auth |

## Auth Error Handling
- **401 on any post-auth endpoint:** Attempt token refresh. If refresh fails, clear session and redirect to SCR-005 (login).
- **WebSocket close code 4001:** Clear session and redirect to login.
- **WebSocket close code 4003:** Show forbidden error message, do not redirect.
