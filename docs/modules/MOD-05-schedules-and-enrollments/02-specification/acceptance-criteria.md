# Acceptance Criteria

## Function-Level Acceptance

### FUN-05-01
- Given valid day filter, returns matching schedules.
- Given invalid query params, returns validation error.

### FUN-05-02
- Given existing schedule ID, returns schedule payload.
- Given unknown schedule ID, returns `404`.

### FUN-05-03
- Given valid admin request, schedule is created (`201`).
- Given invalid room/faculty/time values, returns validation error.
- Given non-admin caller, returns `403`.

### FUN-05-04
- Given faculty caller, returns only faculty schedules.
- Given student caller, returns only enrolled schedules.

### FUN-05-05
- Given valid schedule ID, returns enrolled students list.
- Given unknown schedule ID, returns `404`.

## Module-Level Acceptance
- Schedule/day filters are correct and stable.
- Enrollment relationships are enforced by DB constraints and API behavior.
- Role-aware schedule views are consistent with screen flows.
