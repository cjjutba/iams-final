# Business Rules

## Attendance State Rules
1. Allowed statuses: `present`, `late`, `absent`, `early_leave`.
2. Attendance row uniqueness is `(student_id, schedule_id, date)`.
3. Check-in is first detection; later detections update session context.

## Query Rules
1. Date filters are inclusive and validated.
2. Today's attendance is scoped to schedule and current date.
3. Personal history returns only own records (student scope).

## Manual Override Rules
1. Faculty role required for manual entries.
2. Manual action must store remarks and actor context where possible.
3. Manual update should not violate uniqueness constraint.

## Access Rules
1. Student cannot access faculty-only endpoints.
2. Faculty cannot query unrelated class data without permission.
3. Admin behavior follows policy-defined elevated access.
