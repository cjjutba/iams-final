# Test Strategy (MOD-05)

## Scope
Validate schedule query accuracy, enrollment integrity, role-aware views, creation validation rules, Supabase JWT auth enforcement, timezone handling, and access control on roster endpoints.

## Test Types
- Unit tests: schedule validation, filter logic, role-based query resolution, time comparison logic, day_of_week mapping.
- Integration tests: `/api/v1/schedules/*` endpoint behavior with Supabase JWT auth.
- E2E checks: student/faculty schedule screens and roster access.

## Priority Test Areas
1. Day/time filter correctness (day_of_week 0-6, deterministic sort order).
2. `GET /schedules/me` role-specific behavior (faculty vs student).
3. Enrollment roster consistency and access control.
4. Create schedule validation and admin authorization.
5. Supabase JWT auth enforcement (401 on missing/invalid token).
6. Admin-only access enforcement (403 on non-admin POST).
7. Roster access control (403 on unauthorized viewer).
8. Timezone configuration and time comparison consistency.
9. Enrollment lifecycle (cascade deletion on student removal).

## Exit Criteria
- All critical schedule module tests pass.
- No blocker/high defects in role/access or data mapping logic.
- Auth verification: all endpoints return 401 for missing JWT.
- Admin-only enforcement: POST /schedules returns 403 for non-admin.
- Roster access control verified for all role combinations.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
