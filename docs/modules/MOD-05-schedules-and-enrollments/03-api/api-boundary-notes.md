# API Boundary Notes

## Owned by MOD-05
- `/api/v1/schedules` endpoint family and roster retrieval behavior.

## Auth Boundary
- All MOD-05 endpoints use **Supabase JWT** (`Authorization: Bearer <token>`).
- Auth middleware validates JWT and extracts `sub` (user ID) and `role` claims.
- Role-based access control is enforced at the router/service level (not middleware-only).
- MOD-05 does NOT use API key auth (that is MOD-03/MOD-04 edge device pattern).

## Related but Owned by Other Modules
- Attendance APIs in `MOD-06` consume `schedule_id` and timing semantics to record attendance.
- Presence APIs in `MOD-07` consume active schedule and enrolled student context for presence scoring.
- Import/seed logic for schedule/enrollment CSV is owned by `MOD-11`.
- Edge device in `MOD-04` sends `room_id` in `/face/process` payload; backend uses rooms→schedules mapping to infer active schedule context.

## MOD-04 Edge Device Integration
When the edge device sends a face detection to `POST /api/v1/face/process` with a `room_id`, the backend:
1. Looks up which schedules are assigned to that room.
2. Determines which schedule is "current" based on `day_of_week` and `[start_time, end_time]` window.
3. Uses the active schedule's enrolled students list to scope attendance recording.

## MOD-02 User Deletion Coordination
When a student is deleted via MOD-02, all enrollments for that student are cascade-deleted. This means:
- The student is automatically removed from all class rosters.
- No manual cleanup needed by admin.
- Historical attendance records (MOD-06) may reference the deleted student but are preserved.

## Enrollment Scope Note
MOD-05 MVP does NOT expose enrollment creation/deletion APIs. Enrollments are managed by:
- MOD-11 import scripts (bulk CSV load).
- Direct DB operations (future: admin dashboard).

## Coordination Rule
Changes to schedule identity or timing fields must be synchronized with attendance, presence, and import modules.
