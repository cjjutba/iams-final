# Folder and File Mapping

## Backend Expected Touchpoints
| File | Purpose |
|---|---|
| `backend/app/routers/websocket.py` | WebSocket endpoint (`WS /ws/{user_id}`) with JWT auth |
| `backend/app/services/notification_service.py` | Connection map management, event publishing, fanout |
| `backend/app/schemas/websocket.py` | Pydantic schemas for event payloads (if used for validation) |
| `backend/app/services/attendance_service.py` | Publisher trigger source for `attendance_update` (MOD-06) |
| `backend/app/services/presence_service.py` | Publisher trigger source for `early_leave` (MOD-07) |
| `backend/app/utils/dependencies.py` | Supabase JWT auth middleware (`get_current_user`) |

## Mobile Expected Touchpoints
| File | Purpose |
|---|---|
| `mobile/src/services/websocketService.ts` | WebSocket client, connection management, reconnect logic |
| `mobile/src/store/notificationStore.ts` | Zustand store for notification/event state |
| `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx` | SCR-021 — live attendance view |
| `mobile/src/screens/faculty/FacultyEarlyLeaveAlertsScreen.tsx` | SCR-025 — early-leave alert feed |
| `mobile/src/screens/faculty/FacultyNotificationsScreen.tsx` | SCR-029 — faculty notification feed |
| `mobile/src/screens/student/StudentNotificationsScreen.tsx` | SCR-018 — student notification feed |

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/implementation.md`
- `docs/main/prd.md`
- `docs/modules/MOD-08-realtime-notifications-and-websocket/`
