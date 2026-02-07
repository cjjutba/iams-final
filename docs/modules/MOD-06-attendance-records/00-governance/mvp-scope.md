# MVP Scope

## In Scope
- Mark attendance from recognition events.
- Retrieve today's attendance for class.
- Retrieve personal student attendance history.
- Retrieve filtered attendance history for class context.
- Manual attendance entry by faculty.
- Live attendance roster endpoint.

## Out of Scope
- Advanced report export pipelines.
- Complex analytics/trend dashboards.
- Early leave detection algorithm internals (MOD-07).

## MVP Constraints
- Attendance statuses: `present`, `late`, `absent`, `early_leave`.
- Uniqueness constraint: `(student_id, schedule_id, date)`.
- Manual entry is faculty-restricted.

## MVP Gate Criteria
- `FUN-06-01` through `FUN-06-06` implemented and tested.
- Duplicate marking prevention verified.
- Manual override and history filters validated.
