# Integration Points

## Mobile Screen Files
| File | Screen ID | Auth |
|---|---|---|
| `mobile/src/screens/SplashScreen.tsx` | SCR-001 | Pre-auth |
| `mobile/src/screens/onboarding/OnboardingScreen.tsx` | SCR-002 | Pre-auth |
| `mobile/src/screens/auth/WelcomeScreen.tsx` | SCR-003 | Pre-auth |
| `mobile/src/screens/auth/StudentLoginScreen.tsx` | SCR-004 | Pre-auth |
| `mobile/src/screens/auth/ForgotPasswordScreen.tsx` | SCR-006 | Pre-auth |
| `mobile/src/screens/auth/StudentRegisterStep1Screen.tsx` | SCR-007 | Pre-auth |
| `mobile/src/screens/auth/StudentRegisterStep2Screen.tsx` | SCR-008 | Pre-auth |
| `mobile/src/screens/auth/StudentRegisterStep3Screen.tsx` | SCR-009 | Post-auth |
| `mobile/src/screens/auth/StudentRegisterReviewScreen.tsx` | SCR-010 | Post-auth |
| `mobile/src/screens/student/StudentHomeScreen.tsx` | SCR-011 | Post-auth |
| `mobile/src/screens/student/StudentScheduleScreen.tsx` | SCR-012 | Post-auth |
| `mobile/src/screens/student/StudentAttendanceHistoryScreen.tsx` | SCR-013 | Post-auth |
| `mobile/src/screens/student/StudentAttendanceDetailScreen.tsx` | SCR-014 | Post-auth |
| `mobile/src/screens/student/StudentProfileScreen.tsx` | SCR-015 | Post-auth |
| `mobile/src/screens/student/StudentEditProfileScreen.tsx` | SCR-016 | Post-auth |
| `mobile/src/screens/student/StudentFaceReregisterScreen.tsx` | SCR-017 | Post-auth |
| `mobile/src/screens/student/StudentNotificationsScreen.tsx` | SCR-018 | Post-auth |

## Mobile Service/State Files
| File | Purpose |
|---|---|
| `mobile/src/services/api.ts` | Axios instance with JWT interceptors (auto-attach Bearer token, 401 refresh) |
| `mobile/src/services/authService.ts` | Auth API methods (login, register, refresh, verifyStudentId) |
| `mobile/src/services/faceService.ts` | Face API methods (register, getStatus) |
| `mobile/src/services/websocketService.ts` | WebSocket client (JWT via `token` query param, reconnect with backoff) |
| `mobile/src/store/authStore.ts` | Auth session and token state (Zustand) |
| `mobile/src/store/attendanceStore.ts` | Attendance data and filters (Zustand) |
| `mobile/src/store/scheduleStore.ts` | Schedule data (Zustand) |
| `mobile/src/store/notificationStore.ts` | Notification feed state (Zustand) |

## Backend Contract Providers
| Module | Contract | Auth Note |
|---|---|---|
| MOD-01 | Auth/user APIs (login, register, verify-student-id, refresh, me) | Pre-auth and post-auth endpoints |
| MOD-02 | User management (`PATCH /users/{id}`) | Post-auth |
| MOD-03 | Face APIs (register, status) | Post-auth |
| MOD-05 | Schedule APIs (`GET /schedules/me`) | Post-auth |
| MOD-06 | Attendance APIs (`GET /attendance/me`, `/attendance/today`) | Post-auth |
| MOD-08 | WebSocket stream (`WS /ws/{user_id}?token=<jwt>`) | Post-auth (JWT via query param) |

## Auth Integration
- `api.ts` Axios interceptor: auto-attaches `Authorization: Bearer <token>` to all post-auth requests.
- `api.ts` response interceptor: on 401, attempts `/auth/refresh`, if fails → triggers logout + redirect to login.
- `websocketService.ts`: passes JWT as `token` query parameter (not header) when opening connection.

## Timezone Integration
- Backend timestamps arrive in ISO-8601 with +08:00 offset (Asia/Manila).
- Mobile formats for display using device locale or Asia/Manila setting.
- Date filter parameters sent as `YYYY-MM-DD`.
