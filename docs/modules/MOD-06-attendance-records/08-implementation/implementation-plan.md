# Implementation Plan (MOD-06)

## Phase 1: Foundations
- Verify Supabase JWT auth middleware is in place (shared with MOD-01/MOD-02/MOD-05).
- Verify SQLAlchemy `AttendanceRecord` model exists and matches `database-schema.md`.
- Configure `TIMEZONE` env var (default: Asia/Manila).
- Set up attendance router skeleton at `/api/v1/attendance`.

## Phase 2: Attendance Core
- Implement mark/upsert attendance logic (`FUN-06-01`) with dedup on `(student_id, schedule_id, date)`.
- Implement today's attendance query and summary (`FUN-06-02`) with timezone-aware "today" calculation.
- Enforce Supabase JWT + faculty/admin role on FUN-06-02.

## Phase 3: History APIs
- Implement student attendance history endpoint (`FUN-06-03`) with role-scoped access (JWT sub for students, faculty_id for faculty).
- Implement filtered attendance history endpoint (`FUN-06-04`) with faculty/admin role check and schedule ownership validation.
- Add date range filter validation (start_date ≤ end_date).
- Require Supabase JWT on both endpoints.

## Phase 4: Operational APIs
- Implement faculty manual attendance entry (`FUN-06-05`) with admin/faculty role check.
- Require `remarks` for audit trail. Store `updated_by` (JWT sub), `updated_at`.
- Implement live attendance endpoint (`FUN-06-06`) with active session detection.
- Return 403 for student role on both endpoints.

## Phase 5: Mobile Integration
- Wire student attendance screens (SCR-011, SCR-013, SCR-014) to `GET /attendance/me` and `GET /attendance/today`.
- Wire faculty attendance screens (SCR-019, SCR-021, SCR-024) to `GET /attendance/today`, `GET /attendance/live`, `POST /attendance/manual`.
- Add loading/empty/error states, pull-to-refresh.
- Handle 401 (redirect to login) and 403 (show error message).

## Phase 6: Validation
- Run unit/integration/E2E tests (including auth, role-scoped, timezone scenarios).
- Validate acceptance criteria and update traceability.
- Verify timezone configuration and date comparison consistency.
- Verify audit trail on manual entries (remarks, updated_by, updated_at).
