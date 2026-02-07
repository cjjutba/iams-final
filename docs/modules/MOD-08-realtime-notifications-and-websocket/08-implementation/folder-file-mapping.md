# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/websocket.py`
- `backend/app/services/notification_service.py`
- `backend/app/services/attendance_service.py`
- `backend/app/services/presence_service.py`
- `backend/app/utils/dependencies.py` (auth helpers if needed)

## Mobile Expected Touchpoints
- `mobile/src/services/websocketService.ts`
- `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx`
- `mobile/src/screens/faculty/FacultyNotificationsScreen.tsx`
- `mobile/src/screens/student/StudentNotificationsScreen.tsx`
- `mobile/src/store/` (notification/live state updates)

## Docs to Keep in Sync
- `docs/main/master-blueprint.md`
- `docs/main/api-reference.md`
- `docs/main/technical-specification.md`
- `docs/modules/MOD-08-realtime-notifications-and-websocket/`
