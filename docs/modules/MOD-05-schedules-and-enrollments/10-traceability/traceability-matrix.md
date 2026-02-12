# Traceability Matrix (MOD-05)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-05-01 | GET /schedules?day=1 (Supabase JWT) | schedules, rooms, users | SCR-012, SCR-020 | T05-U1, T05-U6, T05-I1 | backend schedule router/service (with day/room/faculty filters) |
| FUN-05-02 | GET /schedules/{id} (Supabase JWT) | schedules, rooms, users | detail context | T05-I2, T05-I3 | backend schedule service (with faculty name, room name joins) |
| FUN-05-03 | POST /schedules (Supabase JWT, admin-only) | schedules, users, rooms | admin flow | T05-U2, T05-U6, T05-U7, T05-U8, T05-I4, T05-I5, T05-I12, T05-E4 | backend schedule create service (admin role check, FK validation) |
| FUN-05-04 | GET /schedules/me (Supabase JWT, role-scoped) | schedules, enrollments, users | SCR-012, SCR-020 | T05-U3, T05-U4, T05-I6, T05-I7, T05-I13, T05-E1, T05-E2 | backend role-aware schedule query (faculty by faculty_id, student by enrollments) |
| FUN-05-05 | GET /schedules/{id}/students (Supabase JWT, access-controlled) | enrollments, users | roster/detail context | T05-U5, T05-I8, T05-I9, T05-I10, T05-I11, T05-E3 | backend roster query service (admin/faculty/enrolled student access control) |

## Traceability Rule
Every commit touching MOD-05 should map to at least one matrix row.
