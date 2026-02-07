# MOD-07: Presence Tracking and Early Leave

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Continuously monitor in-session presence and detect early leaves.

Functions:
- `FUN-07-01`: Start and manage session state per schedule/date.
- `FUN-07-02`: Run periodic scan (default 60s cycle).
- `FUN-07-03`: Maintain miss counters per student.
- `FUN-07-04`: Flag early leave at threshold.
- `FUN-07-05`: Compute presence score.
- `FUN-07-06`: Return presence logs and early-leave events.

API Contracts:
- `GET /presence/{attendance_id}/logs`
- `GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD`

Data:
- `presence_logs`
- `early_leave_events`
- `attendance_records`
- `schedules`
- `enrollments`

Screens:
- `SCR-022` FacultyClassDetailScreen
- `SCR-023` FacultyStudentDetailScreen
- `SCR-025` FacultyEarlyLeaveAlertsScreen

Done Criteria:
- Session semantics are tied to schedule and date.
- Miss threshold is configurable and documented.
- Early-leave detection is test-covered.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
