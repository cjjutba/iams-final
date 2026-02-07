# Traceability Matrix (MOD-02)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-02-01 | GET /users?role=student&page=1&limit=20 | users | admin flow | T02-I1, T02-I2 | backend users router/service |
| FUN-02-02 | GET /users/{id} | users | SCR-015, SCR-027 | T02-I3, T02-I4 | backend users router/service |
| FUN-02-03 | PATCH /users/{id} | users | SCR-016, SCR-028 | T02-U1, T02-U2, T02-I5, T02-I6, T02-E1, T02-E2 | backend users service + mobile profile flows |
| FUN-02-04 | DELETE /users/{id} | users, face_registrations | admin flow | T02-U4, T02-I7, T02-I8, T02-E4 | backend users lifecycle service |

## Traceability Rule
Every commit touching MOD-02 should map to at least one matrix row.
