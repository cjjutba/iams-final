# Integration Points

## Auth Integration
- Supabase JWT verification via shared `get_current_user` dependency (`backend/app/utils/dependencies.py`).
- Role extraction from JWT claims (`sub` → user_id, `role` → student/faculty/admin).
- All endpoints enforce auth; faculty-only endpoints check role explicitly.

## Backend Integrations
- `backend/app/routers/attendance.py` — REST endpoints with Supabase JWT auth
- `backend/app/schemas/attendance.py` — Pydantic request/response schemas
- `backend/app/services/attendance_service.py` — Business logic, dedup, role-scoped queries
- `backend/app/repositories/attendance_repository.py` — Database queries, upsert operations
- `backend/app/models/attendance_record.py` — SQLAlchemy AttendanceRecord model
- `backend/app/utils/dependencies.py` — Supabase JWT auth middleware

## Mobile Integrations
- Student screens: SCR-011 (home), SCR-013 (history), SCR-014 (detail) — via `mobile/src/services/attendanceService.ts`
- Faculty screens: SCR-019 (home), SCR-021 (live), SCR-024 (manual entry) — via `mobile/src/services/attendanceService.ts`
- Zustand store: `mobile/src/store/attendanceStore.ts`

## Cross-Module Integrations
| Module | Integration | Direction |
|---|---|---|
| MOD-01 (Auth) | Supabase JWT verification, role claims | MOD-01 → MOD-06 |
| MOD-02 (Users) | User data display, cascade deletion | MOD-02 ↔ MOD-06 |
| MOD-03 (Face Recognition) | Recognition result → attendance marking | MOD-03 → MOD-06 |
| MOD-04 (Edge Device) | Edge capture → recognition → attendance flow | MOD-04 → MOD-03 → MOD-06 |
| MOD-05 (Schedules) | Schedule context, enrollment validation, active class detection | MOD-05 → MOD-06 |
| MOD-07 (Presence) | Presence scoring, status updates (present → early_leave) | MOD-06 ↔ MOD-07 |
| MOD-08 (WebSocket) | Real-time attendance update broadcasting | MOD-06 → MOD-08 |

## Timezone Integration
- All date/time operations use `TIMEZONE` env var (default: Asia/Manila).
- "Today" queries derive current date from configured timezone.
- Shared with MOD-05 schedule time window comparisons.
