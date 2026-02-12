# Acceptance Criteria

## Function-Level Acceptance

### FUN-05-01
- Given valid Supabase JWT and `day=1` filter, returns matching schedules sorted by `start_time` ASC.
- Given invalid query params (e.g., `day=9`), returns `400` validation error.
- Given missing/invalid JWT, returns `401`.
- Returns only `is_active=true` schedules by default.

### FUN-05-02
- Given valid JWT and existing schedule ID, returns full schedule payload with faculty name and room name.
- Given unknown schedule ID, returns `404`.
- Given missing/invalid JWT, returns `401`.

### FUN-05-03
- Given valid admin JWT and valid payload (`start_time < end_time`, valid FKs), schedule is created (`201`).
- Given invalid room/faculty/time values, returns `400` validation error.
- Given non-admin JWT, returns `403`.
- Given missing/invalid JWT, returns `401`.
- Created schedule has `is_active=true` by default.
- `faculty_id` must reference a user with `role == "faculty"`.

### FUN-05-04
- Given faculty JWT, returns only schedules where `faculty_id` matches JWT `sub`.
- Given student JWT, returns only schedules where student has enrollment record.
- Given missing/invalid JWT, returns `401`.
- Results sorted by `day_of_week` ASC, `start_time` ASC.
- Returns only `is_active=true` schedules.

### FUN-05-05
- Given valid JWT and valid schedule ID, returns enrolled students list.
- Given unknown schedule ID, returns `404`.
- Given JWT of user not authorized (not admin, not assigned faculty, not enrolled student), returns `403`.
- Given missing/invalid JWT, returns `401`.
- Roster includes: `id` (users.id), `student_id`, `first_name`, `last_name`.

## Module-Level Acceptance
- Schedule/day filters are correct and stable with deterministic sort order.
- Enrollment relationships are enforced by DB constraint `UNIQUE(student_id, schedule_id)`.
- Role-aware schedule views are consistent with screen flows.
- All responses use envelope format: `{ "success": true, "data": {}, "message": "" }`.
- All endpoints return 401 for missing/invalid Supabase JWT.
- Admin-only endpoints return 403 for non-admin callers.
- Timezone configuration applied consistently to time comparisons.
