# Traceability Matrix (MOD-06)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-06-01 | internal mark flow | attendance_records, schedules | n/a direct | T06-U1, T06-U2 | backend attendance service |
| FUN-06-02 | GET /attendance/today | attendance_records, schedules, users | SCR-011, SCR-019 | T06-U3, T06-I1, T06-E1 | backend attendance query service |
| FUN-06-03 | GET /attendance/me | attendance_records, schedules | SCR-013, SCR-014 | T06-I2, T06-I3, T06-E2 | backend student history service |
| FUN-06-04 | GET /attendance | attendance_records, schedules | faculty/report contexts | T06-I4 | backend filtered history service |
| FUN-06-05 | POST /attendance/manual | attendance_records, users | SCR-024 | T06-U4, T06-I5, T06-I6, T06-E4 | backend manual entry service |
| FUN-06-06 | GET /attendance/live/{schedule_id} | attendance_records, schedules, users | SCR-021 | T06-U5, T06-I7, T06-E3 | backend live attendance service |

## Traceability Rule
Every commit touching MOD-06 should map to at least one matrix row.
