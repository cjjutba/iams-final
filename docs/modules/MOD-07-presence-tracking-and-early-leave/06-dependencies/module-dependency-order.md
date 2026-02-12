# Module Dependency Order

## Upstream Dependencies for MOD-07
1. **MOD-01 (Authentication)**
   - Provides Supabase JWT verification middleware (`get_current_user`) for FUN-07-06 endpoints.

2. **MOD-02 (User Management)**
   - User deletion cascades through attendance_records (MOD-06) to presence_logs and early_leave_events.

3. **MOD-03/MOD-04 (Recognition and Edge Ingestion)**
   - Supplies detection outcomes (recognized faces) used in scan processing (FUN-07-02).

4. **MOD-05 (Schedules and Enrollments)**
   - Required for session schedule context (boundaries, day_of_week, start/end times) and enrolled student list.

5. **MOD-06 (Attendance Records)**
   - Required attendance row context for presence logs (FK: `attendance_id` → `attendance_records.id`).
   - MOD-07 updates attendance status (present → early_leave).

## Downstream Consumers
- **MOD-08 (WebSocket/Notifications):** Consumes early-leave events for real-time broadcast to mobile clients.
- **MOD-09 (Student Mobile):** Students indirectly see attendance status updates caused by MOD-07.
- **MOD-10 (Faculty Mobile):** Faculty screens (SCR-022, SCR-023, SCR-025) consume presence logs and early-leave events.

## MOD-07 Before/After Sequence
1. Ensure schedule and attendance foundations are stable (MOD-05, MOD-06).
2. Implement presence scan/counter/flag logic (FUN-07-01 to FUN-07-05).
3. Implement query endpoints (FUN-07-06).
4. Integrate downstream with MOD-08 (realtime alerts) and MOD-10 (faculty screens).

## Internal Function Dependency Order
1. `FUN-07-01` session initialization
2. `FUN-07-02` periodic scans
3. `FUN-07-03` miss-counter updates
4. `FUN-07-04` early-leave flagging
5. `FUN-07-05` score computation
6. `FUN-07-06` logs/events exposure (user-facing API)

## Rationale
Reliable state transitions and counters are prerequisites for accurate event exposure and downstream integration.
