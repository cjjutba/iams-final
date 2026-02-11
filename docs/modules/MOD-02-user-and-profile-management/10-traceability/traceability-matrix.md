# Traceability Matrix (MOD-02)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-02-01 | GET /users | users | admin flow | T02-U6, T02-I1, T02-I2, T02-E5 | backend users router/service (admin + Supabase JWT) |
| FUN-02-02 | GET /users/{id} | users | SCR-015, SCR-027 | T02-I3, T02-I4, T02-I5, T02-E1 | backend users router/service (ownership check + Supabase JWT) |
| FUN-02-03 | PATCH /users/{id} | users | SCR-016, SCR-028 | T02-U1..T02-U5, T02-I6, T02-I7, T02-I8, T02-E2, T02-E3, T02-E4 | backend users service (field rules + email immutability) + mobile profile forms |
| FUN-02-04 | DELETE /users/{id} | users, face_registrations, Supabase Auth | admin flow | T02-U7, T02-I9, T02-I10, T02-I11, T02-I12, T02-E6 | backend users lifecycle service + Supabase Admin API |

## Traceability Rule
Every commit touching MOD-02 should map to at least one matrix row.
