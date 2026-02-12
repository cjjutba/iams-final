# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/schedules.py` — REST endpoints with Supabase JWT auth
- `backend/app/schemas/schedule.py` — Pydantic request/response schemas
- `backend/app/services/schedule_service.py` — Business logic, role-scoped queries, access control
- `backend/app/repositories/schedule_repository.py` — Schedule database queries
- `backend/app/repositories/enrollment_repository.py` — Enrollment database queries, roster joins
- `backend/app/models/schedule.py` — SQLAlchemy Schedule model
- `backend/app/models/enrollment.py` — SQLAlchemy Enrollment model
- `backend/app/models/room.py` — SQLAlchemy Room model
- `backend/app/utils/dependencies.py` — Supabase JWT auth middleware (`get_current_user`)

## Mobile Expected Touchpoints
- `mobile/src/screens/student/StudentScheduleScreen.tsx` — SCR-012
- `mobile/src/screens/faculty/FacultyScheduleScreen.tsx` — SCR-020
- `mobile/src/services/scheduleService.ts` — API client for schedule endpoints
- `mobile/src/store/scheduleStore.ts` — Zustand store for schedule state

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/implementation.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/modules/MOD-05-schedules-and-enrollments/`
