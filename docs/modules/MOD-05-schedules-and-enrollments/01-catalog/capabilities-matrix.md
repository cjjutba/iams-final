# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Admin | list schedules | FUN-05-01 | full scope/filter usage |
| Admin | get schedule by id | FUN-05-02 | full access |
| Admin | create schedule | FUN-05-03 | admin-only |
| Faculty | get own schedules | FUN-05-04 | by `faculty_id` mapping |
| Student | get own schedules | FUN-05-04 | by enrollments mapping |
| Faculty/Admin | get enrolled students | FUN-05-05 | schedule-specific roster |
| Backend | enforce enrollment uniqueness | FUN-05-05 (data context) | uses DB constraint |
