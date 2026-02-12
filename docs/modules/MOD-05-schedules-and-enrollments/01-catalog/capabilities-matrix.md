# Capabilities Matrix

| Actor | Capability | Function ID(s) | Auth Requirement | Notes |
|---|---|---|---|---|
| Admin | list schedules | FUN-05-01 | Supabase JWT | full scope/filter usage |
| Admin | get schedule by id | FUN-05-02 | Supabase JWT | full access |
| Admin | create schedule | FUN-05-03 | Supabase JWT, role=admin | admin-only; returns 403 for non-admin |
| Admin | get enrolled students | FUN-05-05 | Supabase JWT | full roster access |
| Faculty | list schedules | FUN-05-01 | Supabase JWT | filtered view |
| Faculty | get own schedules | FUN-05-04 | Supabase JWT | by `faculty_id` from JWT `sub` |
| Faculty | get enrolled students | FUN-05-05 | Supabase JWT | only for schedules where `faculty_id` matches |
| Student | list schedules | FUN-05-01 | Supabase JWT | filtered view |
| Student | get own schedules | FUN-05-04 | Supabase JWT | by `enrollments` table join |
| Student | get enrolled students | FUN-05-05 | Supabase JWT | only for schedules student is enrolled in |
| Backend | enforce enrollment uniqueness | FUN-05-05 (data context) | n/a | DB constraint `UNIQUE(student_id, schedule_id)` |

## Auth Note
All capabilities require valid Supabase JWT. API key auth is NOT used (that pattern is for edge devices in MOD-03/MOD-04).
