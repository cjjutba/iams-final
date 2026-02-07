# Module Dependency Order

## Upstream Dependencies for MOD-06
1. `MOD-05` Schedules and Enrollments
- Required for schedule context and enrolled students.

2. `MOD-03`/`MOD-04` face recognition + edge ingestion
- Supply recognition events for attendance marking.

3. `MOD-01` Authentication and Identity
- Required for role-aware endpoint access.

## MOD-06 Before/After Sequence
1. Ensure schedule and recognition contexts are stable.
2. Implement attendance recording and query endpoints.
3. Integrate downstream with:
- `MOD-07` presence (status updates/early leave)
- `MOD-08` realtime push events
- mobile modules (`MOD-09`, `MOD-10`)

## Internal Function Dependency Order
1. `FUN-06-01` mark attendance
2. `FUN-06-02` today's attendance
3. `FUN-06-03` my attendance
4. `FUN-06-04` filtered history
5. `FUN-06-05` manual entry
6. `FUN-06-06` live attendance

## Rationale
Reliable marking and base queries should be stable before manual/live operational flows.
