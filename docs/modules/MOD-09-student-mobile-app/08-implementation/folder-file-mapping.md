# Folder and File Mapping

## Expected Mobile Screen Touchpoints
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

## Service and State Touchpoints
| File | Purpose |
|---|---|
| `mobile/src/services/api.ts` | Axios instance with JWT interceptors (auto-attach Bearer, 401 refresh) |
| `mobile/src/services/authService.ts` | Auth API methods (login, register, refresh, verifyStudentId, updateProfile, changePassword) |
| `mobile/src/services/faceService.ts` | Face API methods (register, getStatus) |
| `mobile/src/services/websocketService.ts` | WebSocket client (JWT via `token` query param, reconnect with backoff) |
| `mobile/src/store/authStore.ts` | Auth session and token state (Zustand) |
| `mobile/src/store/attendanceStore.ts` | Attendance data and filters (Zustand) |
| `mobile/src/store/scheduleStore.ts` | Schedule data (Zustand) |
| `mobile/src/store/notificationStore.ts` | Notification feed and connection state (Zustand) |

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/implementation.md`
- `docs/main/prd.md`
- `docs/modules/MOD-09-student-mobile-app/`
