# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-05`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-05` and at least one `FUN-05-*` ID.

## Auth Rules
1. All MOD-05 endpoints require Supabase JWT (`Authorization: Bearer <token>`).
2. `POST /schedules` requires JWT `role` claim == `"admin"`; return 403 if not.
3. `GET /schedules/me` is scoped by JWT `sub` (user ID) and `role` claim — faculty sees own teaching schedules, student sees enrolled schedules.
4. `GET /schedules/{id}/students` is restricted to admin, faculty assigned to that schedule, or enrolled students.
5. Missing or invalid JWT returns 401 on all endpoints.
6. MOD-05 does NOT use API key auth (that pattern is for edge devices in MOD-03/MOD-04).

## Timezone Rules
1. All time comparisons (`start_time`, `end_time` vs current time) use the configured timezone (`TIMEZONE` env var).
2. `start_time` and `end_time` are stored as TIME type (no timezone info); interpretation assumes configured timezone.
3. For JRMSU pilot deployment, timezone is Asia/Manila (+08:00).

## Scope Control
- Implement only `FUN-05-01` to `FUN-05-05` under this module.
- Do not add attendance/presence decision logic in this module.
- Enrollment creation is handled by MOD-11 import scripts (no direct API in MVP).

## Quality Rules
- Schedule time/day filters must be deterministic (sort by `day_of_week` ASC, `start_time` ASC).
- Enrollment uniqueness constraint `(student_id, schedule_id)` must be enforced at DB level.
- Role-based access to schedule data must be validated via Supabase JWT.
- Responses must follow documented API envelope: `{ "success": true, "data": {}, "message": "" }`.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-05 FUN-05-03`
- Any API contract change must update:
  - `03-api/api-inventory.md`
  - relevant endpoint file(s)
  - `10-traceability/traceability-matrix.md`

## Change Process
1. Propose doc updates.
2. Review consistency across API/data/screens/testing docs.
3. Implement code.
4. Run tests.
5. Update traceability and changelog.
