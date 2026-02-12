# Traceability Matrix (MOD-06)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-06-01 | internal mark flow (system/pipeline) | attendance_records, schedules | n/a direct | T06-U1, T06-U2, T06-U8 | backend attendance service (dedup upsert, schedule validation) |
| FUN-06-02 | GET /attendance/today (Supabase JWT, faculty/admin) | attendance_records, schedules, users | SCR-011, SCR-019 | T06-U3, T06-I1, T06-I8, T06-I9, T06-E1 | backend attendance query service (timezone-aware "today", summary, role check) |
| FUN-06-03 | GET /attendance/me (Supabase JWT, role-scoped) | attendance_records, schedules | SCR-013, SCR-014 | T06-U7, T06-I2, T06-I3, T06-I13, T06-E2 | backend role-scoped history (student by JWT sub, faculty by faculty_id) |
| FUN-06-04 | GET /attendance (Supabase JWT, faculty/admin) | attendance_records, schedules | faculty/report contexts | T06-I4, T06-I10 | backend filtered history service (schedule ownership check for faculty) |
| FUN-06-05 | POST /attendance/manual (Supabase JWT, faculty/admin) | attendance_records, users | SCR-024 | T06-U4, T06-U6, T06-I5, T06-I6, T06-I11, T06-E4 | backend manual entry service (audit trail: remarks, updated_by, updated_at) |
| FUN-06-06 | GET /attendance/live/{schedule_id} (Supabase JWT, faculty/admin) | attendance_records, schedules, users | SCR-021 | T06-U5, T06-I7, T06-I12, T06-E3 | backend live attendance service (session detection, MOD-07 integration) |

## Traceability Rule
Every commit touching MOD-06 should map to at least one matrix row.
