# Traceability Matrix (MOD-07)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-07-01 | internal session flow | schedules, enrollments, attendance_records | SCR-022 | T07-U1, T07-S1 | presence service session manager |
| FUN-07-02 | internal scan flow | presence_logs | SCR-022, SCR-023 | T07-S1, T07-S2 | scan evaluator loop |
| FUN-07-03 | internal counter flow | presence_logs, attendance_records | SCR-023 | T07-U2, T07-U3, T07-S3 | counter state logic |
| FUN-07-04 | internal event flow | early_leave_events, attendance_records | SCR-025 | T07-U4, T07-U6, T07-S2, T07-S4 | early-leave event logic |
| FUN-07-05 | internal score flow | attendance_records | SCR-022, SCR-023 | T07-U5 | score computation logic |
| FUN-07-06 | GET /presence/* | presence_logs, early_leave_events | SCR-022, SCR-023, SCR-025 | T07-I1, T07-I2, T07-I3, T07-I4, T07-I5 | presence router/service |

## Traceability Rule
Every commit touching MOD-07 should map to at least one matrix row.
