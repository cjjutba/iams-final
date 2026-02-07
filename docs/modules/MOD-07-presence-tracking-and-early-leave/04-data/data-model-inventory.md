# Data Model Inventory

## Primary Data Stores Used by MOD-07
1. `presence_logs`
2. `early_leave_events`
3. `attendance_records`
4. `schedules`
5. `enrollments`

## Entities
- Per-scan detection logs
- Early-leave event records
- Session-level per-student counters and score aggregates

## Ownership
- Presence/early-leave persistence: presence service
- Attendance base rows: `MOD-06` integration
