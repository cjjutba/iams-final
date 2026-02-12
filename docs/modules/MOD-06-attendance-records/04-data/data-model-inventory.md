# Data Model Inventory

## Primary Data Stores Used by MOD-06
1. `attendance_records` — core attendance data (owned by MOD-06)
2. `schedules` — schedule context, FK target (owned by MOD-05)
3. `users` — student/faculty identity, FK target (owned by MOD-02)
4. `enrollments` — student-schedule relationships (owned by MOD-05)

## Entities
- Attendance row per student/schedule/date (UNIQUE constraint)
- Daily status (`present`, `late`, `absent`, `early_leave`) and check-in/check-out timestamps
- Optional manual `remarks` and audit context (`updated_by`, `updated_at`)
- `presence_score` computed by MOD-07 presence tracking

## Cross-Module Data Flow
| Source | Target | Data | Description |
|---|---|---|---|
| MOD-03 → MOD-06 | Face recognition → attendance marking | student_id, schedule_id, timestamp | Recognition triggers FUN-06-01 |
| MOD-05 → MOD-06 | Schedules → attendance context | schedule_id, day_of_week, start_time, end_time | Active schedule determines class context |
| MOD-06 → MOD-07 | Attendance → presence tracking | attendance_records | Presence scoring reads attendance data |
| MOD-06 → MOD-08 | Attendance → WebSocket | attendance events | Real-time updates broadcast to clients |

## MOD-02 User Deletion Impact
- When a student is deleted via MOD-02, their attendance records should be cascade-deleted.
- Foreign key: `attendance_records.student_id` → `users.id`.

## Data Lifecycle
1. **Creation:** Attendance rows created by FUN-06-01 (recognition pipeline) or FUN-06-05 (manual entry).
2. **Update:** Status may be updated by MOD-07 (e.g., present → early_leave on early departure detection).
3. **Manual Override:** Faculty can upsert with remarks via FUN-06-05 (audit trail stored).
4. **Cascade Deletion:** Student removal (MOD-02) cascades to attendance records.
5. **Schedule Deactivation:** Attendance records preserved when schedule is deactivated (historical data).

## Ownership
- Attendance persistence: backend attendance service/repository (`backend/app/services/attendance_service.py`, `backend/app/repositories/attendance_repository.py`)
- Schedule/user linkage: upstream modules (MOD-05 schedules, MOD-01/02 users)
