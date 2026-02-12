# Screen Inventory

## Module-Scoped Screens
| Screen ID | Screen Name | Auth Required | Realtime Responsibilities |
|---|---|---|---|
| SCR-018 | StudentNotificationsScreen | Authenticated student | Show student-facing notification events (session-end summaries, routed attendance updates). |
| SCR-021 | FacultyLiveAttendanceScreen | Authenticated faculty | Reflect attendance changes and early-leave alerts in active class view. |
| SCR-025 | FacultyEarlyLeaveAlertsScreen | Authenticated faculty | Dedicated feed for early-leave alert events during active sessions. |
| SCR-029 | FacultyNotificationsScreen | Authenticated faculty | Show faculty notification feed for attendance and early-leave events. |

## Screen-to-Function Mapping
| Screen ID | Events Consumed | Functions Involved |
|---|---|---|
| SCR-018 | `session_end`, `attendance_update` (if routed) | FUN-08-01, FUN-08-04, FUN-08-05 |
| SCR-021 | `attendance_update`, `early_leave`, `session_end` | FUN-08-01, FUN-08-02, FUN-08-03, FUN-08-04, FUN-08-05 |
| SCR-025 | `early_leave` | FUN-08-01, FUN-08-03, FUN-08-05 |
| SCR-029 | `attendance_update`, `early_leave`, `session_end` | FUN-08-01, FUN-08-02, FUN-08-03, FUN-08-04, FUN-08-05 |

## Screen Ownership Notes
- Rendering and UX belong to mobile modules (`MOD-09` for student, `MOD-10` for faculty).
- Event transport and payload consistency belong to `MOD-08`.
- WebSocket connection lifecycle (connect, reconnect, heartbeat) managed by `websocketService.ts`.

## Auth Error Handling (Screens)
- **4001 (Unauthorized):** Redirect to login screen. Clear stored JWT. Show "Session expired" message.
- **4003 (Forbidden):** Show error message "Connection forbidden." Do not redirect — likely a bug if `user_id` mismatch occurs.
- **Network disconnect:** Show reconnecting badge/indicator. Auto-retry with exponential backoff.
