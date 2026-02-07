# Traceability Matrix (MOD-10)

| Function ID | APIs/Events | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-10-01 | `/auth/login`, `/auth/refresh`, `/auth/me` | auth session store | SCR-005, SCR-006, SCR-019 | T10-U1, T10-U2, T10-I1 | faculty auth service + route guards |
| FUN-10-02 | `/schedules/me`, `/schedules/{id}/students` | faculty schedule store | SCR-019, SCR-020 | T10-U3, T10-I2 | schedule screens + active class resolver |
| FUN-10-03 | `/attendance/live/{schedule_id}`, `attendance_update` | live roster state | SCR-021, SCR-022, SCR-023 | T10-I3, T10-S1 | live attendance screens + websocket hooks |
| FUN-10-04 | `/attendance/manual`, `/attendance/today` | manual entry draft and roster refresh | SCR-024, SCR-021 | T10-U4, T10-I4, T10-S2 | manual entry form and submit flow |
| FUN-10-05 | `/presence/early-leaves`, `/presence/{attendance_id}/logs`, `/attendance/today`, `session_end`, `early_leave` | alert and summary state | SCR-022, SCR-023, SCR-025, SCR-026 | T10-U5, T10-I5, T10-S3, T10-S4 | alert, detail, and summary views |
| FUN-10-06 | `/users/{id}`, `/auth/me`, `WS /ws/{user_id}` | profile and notification state | SCR-027, SCR-028, SCR-029 | T10-U6, T10-I6, T10-S5 | profile flows + notification feed |

## Traceability Rule
Every commit touching MOD-10 should map to at least one matrix row.
