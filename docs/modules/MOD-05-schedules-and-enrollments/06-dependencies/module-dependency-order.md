# Module Dependency Order

## Upstream Dependencies for MOD-05
1. `MOD-01` Authentication and Identity
- Required for Supabase JWT auth on all schedule endpoints.
- Provides JWT `sub` (user ID) and `role` claims for role-scoped queries.

2. `MOD-02` User and Profile Management
- Required user records for faculty/student references (FK from schedules and enrollments).
- Student deletion triggers cascade deletion of enrollments.

3. `MOD-11` Data Import and Seed Operations
- Provides initial schedule/faculty/student/enrollment datasets via CSV import.
- No direct enrollment API in MVP; MOD-11 is the primary enrollment data source.

## MOD-05 Before/After Sequence
1. Implement auth and user baseline modules (MOD-01 → MOD-02).
2. Implement schedule and enrollment module (MOD-05).
3. Integrate downstream with:
- `MOD-04` edge device (room_id → schedule mapping for active class detection)
- `MOD-06` attendance records (schedule_id, session boundaries)
- `MOD-07` presence tracking (enrolled students, active schedule window)
- `MOD-09`/`MOD-10` mobile schedule screens

## Internal Function Dependency Order
1. `FUN-05-01` list schedules (base read operation)
2. `FUN-05-02` get schedule (single read)
3. `FUN-05-03` create schedule (write, depends on auth middleware)
4. `FUN-05-04` get my schedules (depends on FUN-05-01 patterns + role logic)
5. `FUN-05-05` get schedule students (depends on enrollments data)

## Rationale
Role-scoped schedule retrieval relies on stable schedule core, enrollment mapping, and Supabase JWT auth middleware. MOD-05 must be implemented after MOD-01/MOD-02 but before MOD-06/MOD-07 which consume schedule context.
