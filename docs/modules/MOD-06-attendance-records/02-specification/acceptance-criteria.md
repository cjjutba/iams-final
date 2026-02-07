# Acceptance Criteria

## Function-Level Acceptance

### FUN-06-01
- Given recognized student and active schedule, attendance row is created/updated.
- Duplicate rows for same student/schedule/date are not created.

### FUN-06-02
- Given valid schedule ID, returns today's records and summary.
- Unknown schedule returns `404`.

### FUN-06-03
- Student receives own attendance records for requested date range.
- Invalid date range returns validation error.

### FUN-06-04
- Filtered attendance history returns expected dataset and pagination metadata.
- Unauthorized caller is blocked.

### FUN-06-05
- Faculty can create/update manual attendance with remarks.
- Student caller is blocked with `403`.

### FUN-06-06
- Active session returns live roster payload.
- Inactive session returns consistent non-active response.

## Module-Level Acceptance
- Manual overrides are auditable.
- History and today's views are consistent with source records.
- Live attendance data aligns with session state.
