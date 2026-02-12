# Folder and File Mapping

## Expected Mobile Screen Touchpoints
| File | Screen ID | Auth |
|---|---|---|
| `mobile/src/screens/auth/FacultyLoginScreen.tsx` | SCR-005 | Pre-auth |
| `mobile/src/screens/auth/ForgotPasswordScreen.tsx` | SCR-006 | Pre-auth |
| `mobile/src/screens/faculty/FacultyHomeScreen.tsx` | SCR-019 | Post-auth |
| `mobile/src/screens/faculty/FacultyScheduleScreen.tsx` | SCR-020 | Post-auth |
| `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx` | SCR-021 | Post-auth |
| `mobile/src/screens/faculty/FacultyClassDetailScreen.tsx` | SCR-022 | Post-auth |
| `mobile/src/screens/faculty/FacultyStudentDetailScreen.tsx` | SCR-023 | Post-auth |
| `mobile/src/screens/faculty/FacultyManualEntryScreen.tsx` | SCR-024 | Post-auth |
| `mobile/src/screens/faculty/FacultyAlertsScreen.tsx` | SCR-025 | Post-auth |
| `mobile/src/screens/faculty/FacultyReportsScreen.tsx` | SCR-026 | Post-auth |
| `mobile/src/screens/faculty/FacultyProfileScreen.tsx` | SCR-027 | Post-auth |
| `mobile/src/screens/faculty/FacultyEditProfileScreen.tsx` | SCR-028 | Post-auth |
| `mobile/src/screens/faculty/FacultyNotificationsScreen.tsx` | SCR-029 | Post-auth |

## Service and State Touchpoints
| File | Purpose |
|---|---|
| `mobile/src/services/api.ts` | Axios instance with JWT interceptors (auto-attach Bearer, 401 refresh) |
| `mobile/src/services/authService.ts` | Auth API methods (login, refresh, me, updateProfile, changePassword) |
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
- `docs/modules/MOD-10-faculty-mobile-app/`
