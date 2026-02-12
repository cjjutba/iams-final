# Integration Points

## Mobile Screen Files
| File | Auth | Screen ID |
|---|---|---|
| `mobile/src/screens/auth/FacultyLoginScreen.tsx` | Pre-auth | SCR-005 |
| `mobile/src/screens/auth/ForgotPasswordScreen.tsx` | Pre-auth | SCR-006 |
| `mobile/src/screens/faculty/FacultyHomeScreen.tsx` | Post-auth | SCR-019 |
| `mobile/src/screens/faculty/FacultyScheduleScreen.tsx` | Post-auth | SCR-020 |
| `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx` | Post-auth | SCR-021 |
| `mobile/src/screens/faculty/FacultyClassDetailScreen.tsx` | Post-auth | SCR-022 |
| `mobile/src/screens/faculty/FacultyStudentDetailScreen.tsx` | Post-auth | SCR-023 |
| `mobile/src/screens/faculty/FacultyManualEntryScreen.tsx` | Post-auth | SCR-024 |
| `mobile/src/screens/faculty/FacultyAlertsScreen.tsx` | Post-auth | SCR-025 |
| `mobile/src/screens/faculty/FacultyReportsScreen.tsx` | Post-auth | SCR-026 |
| `mobile/src/screens/faculty/FacultyProfileScreen.tsx` | Post-auth | SCR-027 |
| `mobile/src/screens/faculty/FacultyEditProfileScreen.tsx` | Post-auth | SCR-028 |
| `mobile/src/screens/faculty/FacultyNotificationsScreen.tsx` | Post-auth | SCR-029 |

## Mobile Service/State Files
| File | Purpose |
|---|---|
| `mobile/src/services/api.ts` | Axios instance with JWT interceptors (auto-attach Bearer, 401 refresh) |
| `mobile/src/services/authService.ts` | Auth API methods (login, refresh, me, updateProfile, changePassword) |
| `mobile/src/services/websocketService.ts` | WebSocket client (JWT via `token` query param, reconnect with backoff) |
| `mobile/src/store/authStore.ts` | Auth session and token state (Zustand) |
| `mobile/src/store/attendanceStore.ts` | Attendance data and filters (Zustand) |
| `mobile/src/store/scheduleStore.ts` | Schedule data (Zustand) |
| `mobile/src/store/notificationStore.ts` | Notification feed and connection state (Zustand) |

## Backend Contract Providers
| Module | Contract | Auth Note |
|---|---|---|
| MOD-01 | Auth/user APIs | Pre-auth (login) / Post-auth (refresh, me) |
| MOD-02 | Profile APIs | Post-auth |
| MOD-05 | Schedules | Post-auth |
| MOD-06 | Attendance/manual entry | Post-auth |
| MOD-07 | Presence alerts/logs | Post-auth |
| MOD-08 | WebSocket events | Post-auth (JWT via query param) |

## Auth Integration
- Axios interceptor auto-attaches `Authorization: Bearer <token>` on all post-auth requests.
- On 401: interceptor attempts refresh via `POST /auth/refresh`. If refresh fails, clears SecureStore and redirects to login.
- WebSocket connects via `WS /ws/{user_id}?token=<jwt>` (JWT in query param, not header).

## Timezone Integration
- All timestamp fields from backend use ISO-8601 with +08:00 offset (Asia/Manila).
- Active class resolution uses local timezone comparison.
- Date filters use YYYY-MM-DD format.
