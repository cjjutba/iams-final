# Integration Points

## Backend Integrations
- Schedule router/service/repository layers
- Enrollment repository joins
- Auth dependency middleware for role checks

## Mobile Integrations
- Student and faculty schedule screens
- Optional class detail views that consume roster endpoint

## Cross-Module Integrations
- `MOD-06` attendance uses `schedule_id` and timing semantics
- `MOD-07` presence tracking uses enrolled students and active schedule
- `MOD-11` import scripts seed schedules and enrollments
