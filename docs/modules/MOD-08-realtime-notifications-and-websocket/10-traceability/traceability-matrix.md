# Traceability Matrix (MOD-08)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-08-01 | WS /ws/{user_id} (Supabase JWT, all roles) | connection map | SCR-018, SCR-021, SCR-025, SCR-029 | T08-U1, T08-U2, T08-U7, T08-U8, T08-I1, T08-S5 | websocket router + JWT auth + connection manager |
| FUN-08-02 | event: attendance_update (system-internal) | payload schema | SCR-021, SCR-029 | T08-U3, T08-I1, T08-I7, T08-S1 | notification service publisher (called by MOD-06) |
| FUN-08-03 | event: early_leave (system-internal) | payload schema | SCR-021, SCR-025, SCR-029 | T08-U4, T08-I2, T08-I7, T08-S2 | notification service publisher (called by MOD-07) |
| FUN-08-04 | event: session_end (system-internal) | payload schema | SCR-018, SCR-021, SCR-029 | T08-U5, T08-I3, T08-I7, T08-I8, T08-S3 | session-end publisher hook |
| FUN-08-05 | WS /ws/{user_id} lifecycle | connection map lifecycle | SCR-018, SCR-021, SCR-025, SCR-029 | T08-U6, T08-U9, T08-I4, T08-I5, T08-I6, T08-S4 | connection cleanup + heartbeat + reconnect handling |

## Traceability Rule
Every commit touching MOD-08 should map to at least one matrix row.
