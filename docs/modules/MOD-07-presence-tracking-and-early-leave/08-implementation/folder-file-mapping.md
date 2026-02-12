# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/presence.py` — REST endpoints with Supabase JWT auth
- `backend/app/schemas/presence.py` — Pydantic request/response schemas
- `backend/app/services/presence_service.py` — Presence scan loop, counter logic, score computation
- `backend/app/services/tracking_service.py` — DeepSORT tracking integration
- `backend/app/repositories/presence_repository.py` — Database queries for presence logs/events
- `backend/app/repositories/attendance_repository.py` — Attendance status update (present → early_leave)
- `backend/app/models/presence_log.py` — SQLAlchemy PresenceLog model
- `backend/app/models/early_leave_event.py` — SQLAlchemy EarlyLeaveEvent model
- `backend/app/utils/dependencies.py` — Supabase JWT auth middleware (`get_current_user`)

## Mobile/Client Expected Touchpoints
- `mobile/src/screens/faculty/FacultyClassDetailScreen.tsx` — SCR-022
- `mobile/src/screens/faculty/FacultyStudentDetailScreen.tsx` — SCR-023
- `mobile/src/screens/faculty/FacultyEarlyLeaveAlertsScreen.tsx` — SCR-025
- `mobile/src/services/presenceService.ts` — API client for presence endpoints
- `mobile/src/store/presenceStore.ts` — Zustand store for presence state

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/implementation.md`
- `docs/main/prd.md`
- `docs/modules/MOD-07-presence-tracking-and-early-leave/`
