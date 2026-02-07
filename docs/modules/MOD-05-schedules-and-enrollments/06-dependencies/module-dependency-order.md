# Module Dependency Order

## Upstream Dependencies for MOD-05
1. `MOD-01` Authentication and Identity
- Required for role-aware schedule access.

2. `MOD-02` User and Profile Management
- Required user records for faculty/student references.

3. `MOD-11` Data Import and Seed Operations
- Provides initial schedule/faculty/student datasets.

## MOD-05 Before/After Sequence
1. Implement auth and user baseline modules.
2. Implement schedule and enrollment module.
3. Integrate downstream with:
- `MOD-06` attendance records
- `MOD-07` presence tracking
- `MOD-09`/`MOD-10` schedule screens

## Internal Function Dependency Order
1. `FUN-05-01` list schedules
2. `FUN-05-02` get schedule
3. `FUN-05-03` create schedule
4. `FUN-05-04` get my schedules
5. `FUN-05-05` get schedule students

## Rationale
Role-scoped schedule retrieval relies on stable schedule core and enrollment mapping.
