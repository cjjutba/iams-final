# Data Model Inventory

## Local Mobile Data Domains
| Domain | Store | Auth Context | Description |
|---|---|---|---|
| Auth session state | authStore | Post-auth | Token metadata, user identity, auth status |
| Registration draft state | registrationStore | Pre-auth → Post-auth | Step-wise inputs during registration |
| Attendance and schedule view state | attendanceStore, scheduleStore | Post-auth | Fetched data and UI filters |
| Profile form state | profileStore | Post-auth | Profile details and edit state |
| Notification feed state | notificationStore | Post-auth | WebSocket events and connection state |
| UI state flags | Per-screen | Both | Loading, empty, error indicators |

## Backend Data Domains (Consumed via API)
| Domain | Backend Table | API Endpoint | Auth |
|---|---|---|---|
| Student records | `student_records` | `/auth/verify-student-id` | Pre-auth |
| Users | `users` | `/auth/me`, `/users/{id}` | Post-auth |
| Face registrations | `face_registrations` | `/face/status`, `/face/register` | Post-auth |
| Schedules | `schedules` | `/schedules/me` | Post-auth |
| Attendance records | `attendance_records` | `/attendance/me`, `/attendance/today` | Post-auth |
| Notification events | (via WebSocket stream) | `WS /ws/{user_id}` | Post-auth |

## Mobile File Paths
| File | Purpose |
|---|---|
| `mobile/src/store/authStore.ts` | Auth session and token state |
| `mobile/src/store/attendanceStore.ts` | Attendance data and filters |
| `mobile/src/store/scheduleStore.ts` | Schedule data |
| `mobile/src/store/notificationStore.ts` | Notification feed state |
| `mobile/src/services/api.ts` | Axios instance with interceptors |
| `mobile/src/services/authService.ts` | Auth API methods |
| `mobile/src/services/faceService.ts` | Face API methods |
| `mobile/src/services/websocketService.ts` | WebSocket client |

## Timezone Note
All timestamps from backend use ISO-8601 with +08:00 offset. Mobile should format for display accordingly. API field names use snake_case (e.g., `check_in_time`, `start_time`).

## Module Note
Module 9 primarily owns client-side state and does not own backend table schemas. Mobile does not call Supabase directly — all data access goes through backend REST API.
