# Module Dependency Order

## Upstream Dependencies for MOD-07
1. `MOD-05` Schedules and Enrollments
- Required for session schedule context and enrolled students.

2. `MOD-06` Attendance Records
- Required attendance row context for presence logs/events.

3. `MOD-03`/`MOD-04` Recognition and edge ingestion
- Supplies detection outcomes used in scan processing.

## MOD-07 Before/After Sequence
1. Ensure schedule and attendance foundations are stable.
2. Implement presence scan/counter/flag logic.
3. Integrate downstream with:
- `MOD-08` realtime alerts
- faculty detail and alert screens (`MOD-10`)

## Internal Function Dependency Order
1. `FUN-07-01` session initialization
2. `FUN-07-02` periodic scans
3. `FUN-07-03` miss-counter updates
4. `FUN-07-04` early-leave flagging
5. `FUN-07-05` score computation
6. `FUN-07-06` logs/events exposure

## Rationale
Reliable state transitions and counters are prerequisites for accurate event exposure.
