# Module Dependency Order

## Upstream Dependencies for MOD-06
1. **MOD-01 Authentication and Identity**
   - Supabase JWT auth middleware (`get_current_user` dependency).
   - Role claims in JWT (`sub`, `role`) for access control.
   - Required for all MOD-06 endpoints.

2. **MOD-02 User Management**
   - User data (student_id, names) for attendance record display.
   - User deletion cascades to attendance records (FK: student_id → users.id).

3. **MOD-05 Schedules and Enrollments**
   - Schedule context (schedule_id, day_of_week, start_time, end_time) for attendance scoping.
   - Enrollment data for student-schedule relationship validation.
   - Active schedule detection for "current class" inference.

4. **MOD-03/MOD-04 Face Recognition + Edge Ingestion**
   - Recognition events trigger FUN-06-01 attendance marking.
   - Edge device → recognition pipeline → attendance marking flow.

## Downstream Consumers of MOD-06
- **MOD-07 (Presence Tracking):** Reads attendance records for presence scoring and early-leave detection.
- **MOD-08 (WebSocket/Realtime):** Broadcasts attendance update events to mobile clients.
- **MOD-09 (Student Mobile App):** Displays attendance data on student screens (SCR-011, SCR-013, SCR-014).
- **MOD-10 (Faculty Mobile App):** Displays attendance data on faculty screens (SCR-019, SCR-021, SCR-024).

## MOD-06 Before/After Sequence
1. Ensure schedule and recognition contexts are stable (MOD-01, MOD-05, MOD-03/04).
2. Implement attendance recording and query endpoints (MOD-06).
3. Integrate downstream with MOD-07, MOD-08, MOD-09, MOD-10.

## Internal Function Dependency Order
1. `FUN-06-01` mark attendance (foundation — system pipeline)
2. `FUN-06-02` today's attendance (base query)
3. `FUN-06-03` my attendance (role-scoped query)
4. `FUN-06-04` filtered history (advanced query)
5. `FUN-06-05` manual entry (write operation)
6. `FUN-06-06` live attendance (real-time integration with MOD-07)

## Rationale
Reliable marking and base queries should be stable before manual/live operational flows. Auth middleware (MOD-01) must be verified before any endpoint implementation.
