# Traceability Matrix (MOD-10)

| Function ID | Auth Type | APIs/Events | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|---|
| FUN-10-01 | Pre-auth → Post-auth | `/auth/login` (pre), `/auth/forgot-password` (pre), `/auth/refresh` (post), `/auth/me` (post) | auth session store (SecureStore) | SCR-005, SCR-006, SCR-019 | T10-U1, T10-U2, T10-U9, T10-I1, T10-I7, T10-S5 | faculty auth service + route guards + Axios interceptors |
| FUN-10-02 | Post-auth (JWT) | `/schedules/me`, `/schedules/{id}/students` | faculty schedule store | SCR-019, SCR-020 | T10-U3, T10-U7, T10-I2, T10-S7 | schedule screens + active class resolver (timezone) |
| FUN-10-03 | Post-auth (JWT) + WebSocket (query param) | `/attendance/live/{schedule_id}`, `attendance_update` (WS) | live roster state | SCR-021, SCR-022, SCR-023 | T10-I3, T10-I6, T10-I9, T10-S1 | live attendance screens + websocket hooks + close codes |
| FUN-10-04 | Post-auth (JWT) | `/attendance/manual`, `/attendance/today` | manual entry draft and roster refresh | SCR-024, SCR-021 | T10-U4, T10-U8, T10-I4, T10-I8, T10-S2 | manual entry form + submit + response envelope |
| FUN-10-05 | Post-auth (JWT) + WebSocket events | `/presence/early-leaves`, `/presence/{attendance_id}/logs`, `/attendance/today`, `/attendance`, `session_end` (WS), `early_leave` (WS) | alert and summary state | SCR-022, SCR-023, SCR-025, SCR-026 | T10-U5, T10-I5, T10-S3, T10-S4 | alert, detail, and summary views + timezone |
| FUN-10-06 | Post-auth (JWT) + WebSocket (query param) | `/users/{id}`, `/auth/me`, `WS /ws/{user_id}?token=<jwt>` | profile and notification state | SCR-027, SCR-028, SCR-029 | T10-U6, T10-I6, T10-S6 | profile flows + notification feed + reconnect |

## Traceability Rule
Every commit touching MOD-10 should map to at least one matrix row.
