# Data Model Inventory

## Primary Data Stores Used by MOD-07
1. `presence_logs` — per-scan detection log entries (owned by MOD-07).
2. `early_leave_events` — early-leave flag records (owned by MOD-07).
3. `attendance_records` — parent attendance context (owned by MOD-06).
4. `schedules` — session schedule boundaries (owned by MOD-05).
5. `enrollments` — student enrollment for session context (owned by MOD-05).

## Entities
- **Per-scan detection logs** — stored in `presence_logs`, FK → `attendance_records.id`.
- **Early-leave event records** — stored in `early_leave_events`, FK → `attendance_records.id`.
- **Session-level per-student counters** — runtime state (miss_count, total_scans, scans_detected) — in-memory during session, persisted via presence_logs aggregation.

## Ownership
- `presence_logs` and `early_leave_events`: owned by MOD-07 presence service.
- `attendance_records`: owned by MOD-06 (MOD-07 updates status field: present → early_leave).
- `schedules` and `enrollments`: owned by MOD-05 (read-only from MOD-07 perspective).

## Backend File Paths
- Model: `backend/app/models/presence_log.py`, `backend/app/models/early_leave_event.py`
- Service: `backend/app/services/presence_service.py`, `backend/app/services/tracking_service.py`
- Repository: `backend/app/repositories/presence_repository.py`

## Cross-Module Data Flow
| Source | Target | Data | Trigger |
|---|---|---|---|
| MOD-03/MOD-04 → MOD-07 | presence_service | Detection results (recognized faces) | Each scan cycle |
| MOD-05 → MOD-07 | presence_service | Schedule boundaries, enrolled students | Session start |
| MOD-06 → MOD-07 | presence_logs | attendance_records.id (FK reference) | Attendance record creation |
| MOD-07 → MOD-06 | attendance_records | Status update (present → early_leave) | Early-leave detection |
| MOD-07 → MOD-08 | WebSocket broadcast | Early-leave event payload | Early-leave flagging |

## MOD-02 User Deletion Impact
- User deletion cascades: `users` → `attendance_records` (MOD-06) → `presence_logs` + `early_leave_events` (MOD-07).
- All presence data for deleted user is removed via FK cascade.

## Data Lifecycle
1. **Session Start:** Presence service reads schedule/enrollment data from MOD-05.
2. **Scan Cycle:** Detection results create `presence_logs` entries per enrolled student.
3. **Threshold Check:** Miss counter reaches threshold → `early_leave_events` record created.
4. **Status Update:** Attendance record status updated to `early_leave` (MOD-06).
5. **Query:** Faculty queries presence logs and early-leave events via FUN-07-06 endpoints.
