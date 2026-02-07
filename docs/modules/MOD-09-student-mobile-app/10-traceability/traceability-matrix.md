# Traceability Matrix (MOD-09)

| Function ID | APIs/Events | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-09-01 | local routing | launch/session flags | SCR-001, SCR-002, SCR-003 | T09-U1, T09-S1, T09-S2 | splash/onboarding/welcome navigation |
| FUN-09-02 | `/auth/login`, `/auth/refresh`, `/auth/me` | secure token storage, auth store | SCR-004, SCR-006, SCR-011 | T09-U2, T09-I1 | auth service + auth store |
| FUN-09-03 | `/auth/verify-student-id`, `/auth/register`, `/face/register` | registration draft state | SCR-007, SCR-008, SCR-009, SCR-010 | T09-U3, T09-U4, T09-I2, T09-S1 | registration screens + validators |
| FUN-09-04 | `/schedules/me`, `/attendance/me`, `/attendance/today` | attendance/schedule stores | SCR-011, SCR-012, SCR-013, SCR-014 | T09-U5, T09-I3, T09-S3 | student home/schedule/history/detail |
| FUN-09-05 | `/auth/me`, `/users/{id}`, `/face/status`, `/face/register` | profile store, face status | SCR-015, SCR-016, SCR-017 | T09-I4, T09-I5 | profile and face re-registration flows |
| FUN-09-06 | `WS /ws/{user_id}` + events | notification store/cache | SCR-018 | T09-U6, T09-I6, T09-S4 | websocket service + notifications screen |

## Traceability Rule
Every commit touching MOD-09 should map to at least one matrix row.
