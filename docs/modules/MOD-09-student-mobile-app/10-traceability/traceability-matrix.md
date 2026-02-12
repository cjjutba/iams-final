# Traceability Matrix (MOD-09)

| Function ID | Auth Type | APIs/Events | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|---|
| FUN-09-01 | Pre-auth (local) | local routing | launch/session flags (AsyncStorage, SecureStore) | SCR-001, SCR-002, SCR-003 | T09-U1, T09-S1, T09-S2 | splash/onboarding/welcome navigation |
| FUN-09-02 | Pre-auth → Post-auth | `POST /auth/login` (pre), `POST /auth/refresh` (post), `GET /auth/me` (post) | secure token storage (SecureStore), auth store | SCR-004, SCR-006, SCR-011 | T09-U2, T09-U9, T09-I1, T09-I7, T09-S5 | auth service + auth store + Axios interceptors |
| FUN-09-03 | Pre-auth (Steps 1-2) / Post-auth (Steps 3-4) | `POST /auth/verify-student-id` (pre), `POST /auth/register` (pre), `POST /face/register` (post) | registration draft state | SCR-007, SCR-008, SCR-009, SCR-010 | T09-U3, T09-U4, T09-I2, T09-I8, T09-S1 | registration screens + validators + step gating |
| FUN-09-04 | Post-auth (JWT) | `GET /schedules/me`, `GET /attendance/me`, `GET /attendance/today` | attendance/schedule stores | SCR-011, SCR-012, SCR-013, SCR-014 | T09-U5, T09-U7, T09-I3, T09-S3, T09-S6 | student home/schedule/history/detail + timezone |
| FUN-09-05 | Post-auth (JWT) | `GET /auth/me`, `PATCH /users/{id}`, `GET /face/status`, `POST /face/register` | profile store, face status | SCR-015, SCR-016, SCR-017 | T09-I4, T09-I5 | profile and face re-registration flows |
| FUN-09-06 | Post-auth (JWT via query param) | `WS /ws/{user_id}?token=<jwt>` + events | notification store/cache | SCR-018 | T09-U6, T09-U8, T09-I6, T09-I9, T09-S4 | websocket service + notifications screen + close codes |

## Traceability Rule
Every commit touching MOD-09 should map to at least one matrix row.
