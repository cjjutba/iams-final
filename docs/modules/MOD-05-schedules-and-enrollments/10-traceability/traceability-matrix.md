# Traceability Matrix (MOD-05)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-05-01 | GET /schedules?day=1 | schedules, rooms, users | SCR-012, SCR-020 | T05-U1, T05-I1 | backend schedule router/service |
| FUN-05-02 | GET /schedules/{id} | schedules, rooms, users | detail context | T05-I2, T05-I3 | backend schedule service |
| FUN-05-03 | POST /schedules | schedules, users, rooms | admin flow | T05-U2, T05-I4, T05-I5, T05-E4 | backend schedule create service |
| FUN-05-04 | GET /schedules/me | schedules, enrollments, users | SCR-012, SCR-020 | T05-U3, T05-U4, T05-I6, T05-I7, T05-E1, T05-E2 | backend role-aware schedule query |
| FUN-05-05 | GET /schedules/{id}/students | enrollments, users | roster/detail context | T05-U5, T05-I8, T05-E3 | backend roster query service |

## Traceability Rule
Every commit touching MOD-05 should map to at least one matrix row.
