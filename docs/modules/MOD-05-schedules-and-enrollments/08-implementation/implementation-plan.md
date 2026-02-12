# Implementation Plan (MOD-05)

## Phase 1: Foundations
- Verify Supabase JWT auth middleware is in place (shared with MOD-01/MOD-02).
- Verify SQLAlchemy models for `Schedule`, `Enrollment`, `Room` exist and match `database-schema.md`.
- Configure `TIMEZONE` env var (default: Asia/Manila).
- Set up schedule router skeleton at `/api/v1/schedules`.

## Phase 2: Schedule Read APIs
- Implement `GET /schedules` with `day`, `room_id`, `faculty_id`, `active_only` query params.
- Implement `GET /schedules/{id}` with full schedule payload (include faculty name, room name via joins).
- Add day/time filter validation (`day_of_week` 0-6).
- Enforce deterministic sort order (`day_of_week` ASC, `start_time` ASC).
- Require Supabase JWT on both endpoints.

## Phase 3: Schedule Write API
- Implement `POST /schedules` with admin authorization (JWT role check).
- Validate payload: `start_time < end_time`, valid `faculty_id` (must be faculty role), valid `room_id`.
- Return 403 for non-admin, 401 for missing JWT.
- Set `is_active=true` by default.

## Phase 4: Role-Aware Retrieval
- Implement `GET /schedules/me` by role context (JWT `sub` and `role`).
  - Faculty: query by `faculty_id`.
  - Student: query via `enrollments` join.
- Implement `GET /schedules/{id}/students` with access control.
  - Admin: full access.
  - Faculty: only own schedules (check `faculty_id`).
  - Student: only enrolled schedules (check enrollment exists).
- Return 403 for unauthorized roster access.

## Phase 5: Mobile Integration
- Connect student schedule screen (`SCR-012`) to `GET /api/v1/schedules/me`.
- Connect faculty schedule screen (`SCR-020`) to `GET /api/v1/schedules/me`.
- Add loading/empty/error states, pull-to-refresh.
- Handle 401 (redirect to login) and 403 (show error message).

## Phase 6: Validation
- Run unit/integration/E2E tests (including auth, role-scoped, roster access scenarios).
- Validate acceptance criteria and update traceability.
- Verify timezone configuration and time comparison consistency.
- Verify enrollment lifecycle (cascade deletion on student removal).
