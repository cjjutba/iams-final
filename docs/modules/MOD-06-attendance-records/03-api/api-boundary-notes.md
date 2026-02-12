# API Boundary Notes

## Owned by MOD-06
- Attendance endpoint family (`/api/v1/attendance/*`) and attendance-record lifecycle behavior.
- All endpoints require Supabase JWT (`Authorization: Bearer <token>`).

## Auth Boundary
- MOD-06 uses **Supabase JWT** for all endpoints (user-facing).
- No API key auth — that pattern is for MOD-03/MOD-04 edge device endpoints only.
- FUN-06-01 (Mark Attendance) is a system/internal operation triggered by the recognition pipeline, not a user-facing REST endpoint.

## Related but Owned by Other Modules
- **MOD-03 (Face Recognition):** Recognition results trigger FUN-06-01 attendance marking. MOD-06 receives student identification from MOD-03.
- **MOD-04 (Edge Device):** Edge device captures feed into recognition pipeline (MOD-03) which ultimately triggers attendance marking (MOD-06).
- **MOD-05 (Schedules/Enrollments):** Provides `schedule_id` context. Active schedule detection (day_of_week + time window) determines which class attendance is marked for. Enrollments table validates student-schedule relationships.
- **MOD-07 (Presence Tracking):** Presence logs and early-leave events are owned by MOD-07. MOD-07 reads attendance records for presence scoring and may update attendance status (e.g., present → early_leave).
- **MOD-08 (WebSocket/Realtime):** Realtime event delivery for attendance updates is owned by MOD-08.

## MOD-02 User Deletion Coordination
- When a student is deleted via MOD-02, their attendance records should be cascade-deleted for data integrity.
- Foreign key: `attendance_records.student_id` → `users.id`.

## Coordination Rule
Any attendance status or payload change must be synchronized with:
- MOD-07 presence and early-leave event contracts.
- MOD-08 websocket event contracts for real-time attendance updates.
- Response envelope format: `{ "success": true, "data": {}, "message": "" }`.
