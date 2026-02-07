# MOD-05: Schedules and Enrollments

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Define class schedules and enroll students per class.

Functions:
- `FUN-05-01`: List schedules by filters/day.
- `FUN-05-02`: Get schedule by ID.
- `FUN-05-03`: Create schedule (admin).
- `FUN-05-04`: Get schedules for current user.
- `FUN-05-05`: Get students assigned to schedule.

API Contracts:
- `GET /schedules?day=1`
- `GET /schedules/{id}`
- `POST /schedules`
- `GET /schedules/me`
- `GET /schedules/{id}/students`

Data:
- `rooms`
- `schedules`
- `enrollments`
- `users`

Screens:
- `SCR-012` StudentScheduleScreen
- `SCR-020` FacultyScheduleScreen

Done Criteria:
- Time/day filters return correct active schedules.
- Enrollment relationships are enforced.
- Schedule ownership and permissions are validated.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
