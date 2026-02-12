# Traceability Matrix (MOD-07)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-07-01 | internal session flow (system-internal) | schedules, enrollments, attendance_records | SCR-022 | T07-U1, T07-U8, T07-S1 | presence service session manager (TIMEZONE-aware) |
| FUN-07-02 | internal scan flow (system-internal) | presence_logs | SCR-022, SCR-023 | T07-S1, T07-S2 | scan evaluator loop (SCAN_INTERVAL) |
| FUN-07-03 | internal counter flow (system-internal) | presence_logs, attendance_records | SCR-023 | T07-U2, T07-U3, T07-S3 | counter state logic (deterministic reset/increment) |
| FUN-07-04 | internal event flow (system-internal) | early_leave_events, attendance_records | SCR-025 | T07-U4, T07-U6, T07-S2, T07-S4 | early-leave event logic (dedup, MOD-06 status update, MOD-08 broadcast) |
| FUN-07-05 | internal score flow (system-internal) | attendance_records | SCR-022, SCR-023 | T07-U5, T07-U7 | score computation logic (zero-scan handling) |
| FUN-07-06 | GET /presence/* (Supabase JWT, faculty/admin) | presence_logs, early_leave_events | SCR-022, SCR-023, SCR-025 | T07-I1, T07-I2, T07-I3, T07-I4, T07-I5, T07-I6, T07-I7, T07-I8, T07-I9, T07-I10, T07-S5 | presence router/service, auth middleware |

## Traceability Rule
Every commit touching MOD-07 should map to at least one matrix row.
