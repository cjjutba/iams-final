# Integration Points

## Auth Integration
- Shared JWT verification from MOD-01 (`get_current_user` dependency in `backend/app/utils/dependencies.py`).
- WebSocket uses JWT via `token` query parameter (not `Authorization` header due to WS handshake limitations).

## Backend File Paths
| File | Purpose |
|---|---|
| `backend/app/routers/websocket.py` | WebSocket endpoint (`WS /ws/{user_id}`) |
| `backend/app/services/notification_service.py` | Connection map management, event publishing |
| `backend/app/services/attendance_service.py` | Publisher trigger source for `attendance_update` (MOD-06) |
| `backend/app/services/presence_service.py` | Publisher trigger source for `early_leave` (MOD-07) |
| `backend/app/utils/dependencies.py` | Supabase JWT auth middleware |
| `backend/app/schemas/websocket.py` | Pydantic schemas for event payloads (if used) |

## Mobile File Paths
| File | Purpose |
|---|---|
| `mobile/src/services/websocketService.ts` | WebSocket client, connection management, reconnect logic |
| `mobile/src/store/notificationStore.ts` | Zustand store for notification/event state |
| `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx` | SCR-021 |
| `mobile/src/screens/faculty/FacultyEarlyLeaveAlertsScreen.tsx` | SCR-025 |
| `mobile/src/screens/faculty/FacultyNotificationsScreen.tsx` | SCR-029 |
| `mobile/src/screens/student/StudentNotificationsScreen.tsx` | SCR-018 |

## Cross-Module Integration
| Module | Integration Type | Description |
|---|---|---|
| MOD-01 | Auth | JWT verification for WebSocket handshake |
| MOD-02 | Lifecycle | User deletion → close WS connection, remove from map |
| MOD-05 | Data | Schedule/enrollment data for recipient resolution |
| MOD-06 | Event trigger | Attendance service calls FUN-08-02 after status transitions |
| MOD-07 | Event trigger | Presence service calls FUN-08-03 after early-leave detection |
| MOD-09 | Consumer | Student mobile app receives events (SCR-018) |
| MOD-10 | Consumer | Faculty mobile app receives events (SCR-021, SCR-025, SCR-029) |

## Timezone Integration
- Event timestamps use `TIMEZONE` env var (default: Asia/Manila, +08:00).
- Shared with MOD-06/MOD-07 — upstream events already include timezone-aware timestamps.

## Config and Runtime
- Backend: heartbeat interval, stale timeout, connection cap, delivery logging toggle.
- Mobile: WebSocket base URL, reconnect delays, retry cap.
- Protocol alignment: `ws://` in development, `wss://` in production.
