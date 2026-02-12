# Test Strategy (MOD-06)

## Scope
Validate attendance mark/upsert behavior, history queries, manual overrides, live class data outputs, auth enforcement (Supabase JWT + role-based access), timezone consistency, and data integrity rules.

## Test Types
- **Unit tests:** Dedup/upsert logic, status transitions, summary calculation, date validation, timezone handling.
- **Integration tests:** Attendance endpoints with Supabase JWT auth, role restrictions (401/403), query parameter validation.
- **E2E checks:** Student/faculty attendance screens, manual entry flow, auth error handling.

## Priority Test Areas
1. Duplicate-prevention rule (UNIQUE constraint on student_id + schedule_id + date).
2. Auth enforcement: 401 for missing/invalid JWT, 403 for insufficient role on all protected endpoints.
3. Role-scoped access: students see only own records, faculty see only own schedules (unless admin).
4. Date-filtered history correctness with timezone consistency.
5. Manual entry permissions, audit fields (remarks, updated_by, updated_at), and status validation.
6. Live attendance payload consistency with MOD-07 presence data.
7. Timezone handling: "today" queries use configured timezone, not UTC.
8. Response envelope format: `message` field present in all success responses.
9. Data integrity: cascade deletion on user removal, schedule deactivation preserves records.

## Exit Criteria
- All critical attendance tests pass (unit + integration).
- Auth enforcement verified: all protected endpoints return 401/403 as specified.
- No blocker/high defects in status/update logic.
- Timezone consistency validated for date comparisons.
- Acceptance criteria in `02-specification/acceptance-criteria.md` are satisfied.
