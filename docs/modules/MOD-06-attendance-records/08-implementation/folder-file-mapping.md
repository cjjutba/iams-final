# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/attendance.py` — REST endpoints with Supabase JWT auth
- `backend/app/schemas/attendance.py` — Pydantic request/response schemas
- `backend/app/services/attendance_service.py` — Business logic, dedup, role-scoped queries
- `backend/app/repositories/attendance_repository.py` — Database queries, upsert operations
- `backend/app/models/attendance_record.py` — SQLAlchemy AttendanceRecord model
- `backend/app/utils/dependencies.py` — Supabase JWT auth middleware (`get_current_user`)

## Mobile Expected Touchpoints
- `mobile/src/screens/student/StudentHomeScreen.tsx` — SCR-011
- `mobile/src/screens/student/StudentAttendanceHistoryScreen.tsx` — SCR-013
- `mobile/src/screens/student/StudentAttendanceDetailScreen.tsx` — SCR-014
- `mobile/src/screens/faculty/FacultyHomeScreen.tsx` — SCR-019
- `mobile/src/screens/faculty/FacultyLiveAttendanceScreen.tsx` — SCR-021
- `mobile/src/screens/faculty/FacultyManualEntryScreen.tsx` — SCR-024
- `mobile/src/services/attendanceService.ts` — API client for attendance endpoints
- `mobile/src/store/attendanceStore.ts` — Zustand store for attendance state

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/implementation.md`
- `docs/modules/MOD-06-attendance-records/`
