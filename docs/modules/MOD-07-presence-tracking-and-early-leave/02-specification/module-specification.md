# Module Specification

## Module ID
`MOD-07`

## Purpose
Continuously monitor in-session presence and detect early leaves.

## Auth Context
- **System-Internal (FUN-07-01 to FUN-07-05):** Backend service functions — no HTTP endpoints, no JWT.
- **User-Facing API (FUN-07-06):** Supabase JWT required, faculty/admin role. Base path: `/api/v1/presence`.

## Function Categories
- **System-Internal**: FUN-07-01 to FUN-07-05 (scan loop, counters, flagging — invoked by presence service).
- **User-Facing API**: FUN-07-06 (exposed as GET /presence/* HTTP endpoints).

## Core Functions
- `FUN-07-01`: Start and manage session state per schedule/date (system-internal).
- `FUN-07-02`: Run periodic scan at `SCAN_INTERVAL` (default: 60s) (system-internal).
- `FUN-07-03`: Maintain miss counters per student (system-internal).
- `FUN-07-04`: Flag early leave at `EARLY_LEAVE_THRESHOLD` (default: 3) (system-internal).
- `FUN-07-05`: Compute presence score (system-internal).
- `FUN-07-06`: Return presence logs and early-leave events (Supabase JWT, faculty/admin).

## API Contracts
- `GET /api/v1/presence/{attendance_id}/logs` — Supabase JWT, faculty/admin.
- `GET /api/v1/presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` — Supabase JWT, faculty/admin.

## Data Dependencies
- `presence_logs` (FK → `attendance_records.id`)
- `early_leave_events` (FK → `attendance_records.id`, `schedules.id`)
- `attendance_records` (MOD-06)
- `schedules` (MOD-05)
- `enrollments` (MOD-05)

## Screen Dependencies
- `SCR-022` FacultyClassDetailScreen — session summary, presence overview.
- `SCR-023` FacultyStudentDetailScreen — scan timeline, presence log detail.
- `SCR-025` FacultyEarlyLeaveAlertsScreen — early-leave flagged students list.

## Cross-Module Coordination
- **MOD-03/MOD-04 → MOD-07:** Recognition pipeline provides scan detection results.
- **MOD-05 → MOD-07:** Schedule and enrollment data provide session context.
- **MOD-06 → MOD-07:** Attendance records that presence logs FK-reference.
- **MOD-07 → MOD-06:** Early-leave detection updates attendance status (present → early_leave).
- **MOD-07 → MOD-08:** Early-leave events trigger WebSocket broadcast to mobile clients.
- **MOD-02 → MOD-07:** User deletion cascades through attendance_records to presence_logs and early_leave_events.

## Done Criteria
- Session semantics are tied to schedule and date using configured `TIMEZONE`.
- Miss threshold is configurable via `EARLY_LEAVE_THRESHOLD` env var and documented.
- Early-leave detection is test-covered.
- Auth enforcement verified: 401 for missing/invalid JWT, 403 for student role on FUN-07-06.
- Response envelope consistent: `{ "success": true, "data": {}, "message": "" }`.
- Timezone handling: session boundaries use configured `TIMEZONE` (default: Asia/Manila).
