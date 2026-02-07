# Traceability Matrix (MOD-01)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-01-01 | POST /auth/verify-student-id | university validation source | SCR-007 | T01-I1, T01-I2 | backend auth router/service |
| FUN-01-02 | POST /auth/register | users + validation source | SCR-008, SCR-010 | T01-I3, T01-I4, T01-E1 | backend auth router/service |
| FUN-01-03 | POST /auth/login | users | SCR-004, SCR-005 | T01-U1..T01-U4, T01-I5, T01-I6, T01-E2, T01-E3 | backend auth + mobile auth integration |
| FUN-01-04 | POST /auth/refresh | token model | session layer | T01-U5, T01-I7 | backend auth + mobile session manager |
| FUN-01-05 | GET /auth/me | users | app startup, SCR-004, SCR-005 | T01-I8, T01-I9, T01-E2 | backend protected route + mobile profile load |

## Traceability Rule
Every commit touching MOD-01 should map to at least one matrix row.
