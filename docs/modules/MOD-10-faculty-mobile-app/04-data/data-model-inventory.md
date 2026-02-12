# Data Model Inventory

## Local Mobile Data Domains
| Domain | Auth Context | Description |
|---|---|---|
| Auth session state | Post-auth | Tokens, faculty identity, role (stored in SecureStore) |
| Faculty schedule state | Post-auth | Schedule list, active class, selected class |
| Live attendance roster | Post-auth | Real-time student attendance for active class |
| Manual entry draft | Post-auth | Form state for manual attendance submission |
| Early-leave alert state | Post-auth | Alert feed and class summary data |
| Profile edit state | Post-auth | Faculty profile and edit form state |
| Notification feed state | Post-auth | WebSocket events and connection status |
| UI state flags | Both | Loading, empty, error per screen |

## Backend Data Domains (Consumed)
| Table | API Endpoint | Auth |
|---|---|---|
| `users` | `GET /auth/me`, `GET/PATCH /users/{id}` | Post-auth |
| `schedules` | `GET /schedules/me` | Post-auth |
| `enrollments` | `GET /schedules/{id}/students` | Post-auth |
| `attendance_records` | `GET /attendance/live/{id}`, `GET /attendance/today`, `POST /attendance/manual` | Post-auth |
| `presence_logs` | `GET /presence/{attendance_id}/logs` | Post-auth |
| `early_leave_events` | `GET /presence/early-leaves` | Post-auth |

## Mobile File Paths
| File | Purpose |
|---|---|
| `mobile/src/services/api.ts` | Axios instance with JWT interceptors |
| `mobile/src/services/authService.ts` | Auth API methods |
| `mobile/src/services/websocketService.ts` | WebSocket client (JWT via query param) |
| `mobile/src/store/authStore.ts` | Auth session and token state |
| `mobile/src/store/attendanceStore.ts` | Attendance data |
| `mobile/src/store/scheduleStore.ts` | Schedule data |
| `mobile/src/store/notificationStore.ts` | Notification feed state |

## Timezone Note
- All timestamp fields from backend use ISO-8601 with +08:00 offset.
- Mobile does NOT access Supabase directly — all data via backend REST API.

## Module Note
Module 10 owns client-side behavior and does not own backend table schemas.
