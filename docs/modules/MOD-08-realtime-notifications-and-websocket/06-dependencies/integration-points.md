# Integration Points

## Backend
- `backend/app/routers/websocket.py`
- `backend/app/services/notification_service.py`
- `backend/app/services/attendance_service.py` (publisher trigger source)
- `backend/app/services/presence_service.py` (publisher trigger source)

## Mobile
- `mobile/src/services/websocketService.ts`
- `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx`
- `mobile/src/screens/faculty/FacultyNotificationsScreen.tsx`
- `mobile/src/screens/student/StudentNotificationsScreen.tsx`

## Config and Runtime
- Backend realtime heartbeat and timeout config
- Mobile WebSocket base URL and reconnect policy
