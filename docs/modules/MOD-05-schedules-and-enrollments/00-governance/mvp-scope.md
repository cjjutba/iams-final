# MVP Scope

## In Scope
- List schedules by day/filter.
- Get one schedule by ID.
- Create schedule (admin).
- Get schedules for current user.
- Get students enrolled in a schedule.

## Out of Scope
- Full admin UI for schedule maintenance.
- Automatic schedule conflict optimization.
- Semester planner automation.

## MVP Constraints
- Schedule uses `day_of_week`, `start_time`, `end_time`, and active status.
- Enrollment uses unique `(student_id, schedule_id)`.
- Times must be interpreted in a consistent timezone.

## MVP Gate Criteria
- `FUN-05-01` through `FUN-05-05` implemented and tested.
- Role-aware schedule retrieval works for student/faculty.
- Enrollment lookups match roster data.
