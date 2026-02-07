# Test Cases (MOD-01)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T01-U1 | FUN-01-03 | hash password | hash generated |
| T01-U2 | FUN-01-03 | verify correct password | true |
| T01-U3 | FUN-01-03 | verify wrong password | false |
| T01-U4 | FUN-01-03 | decode expired token | exception/invalid |
| T01-U5 | FUN-01-04 | validate invalid refresh token | unauthorized |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T01-I1 | POST /auth/verify-student-id | valid student_id | `200`, `valid: true` |
| T01-I2 | POST /auth/verify-student-id | unknown student_id | `200`, `valid: false` |
| T01-I3 | POST /auth/register | valid payload | `201`, user created |
| T01-I4 | POST /auth/register | duplicate email | `400` |
| T01-I5 | POST /auth/login | valid credentials | `200`, tokens |
| T01-I6 | POST /auth/login | wrong password | `401` |
| T01-I7 | POST /auth/refresh | valid refresh token | `200`, new token |
| T01-I8 | GET /auth/me | valid access token | `200`, user profile |
| T01-I9 | GET /auth/me | missing token | `401` |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T01-E1 | student registration step1->step2->review register | successful account creation |
| T01-E2 | student login then `/auth/me` | session restored and routed |
| T01-E3 | faculty login with pre-seeded account | login success |
| T01-E4 | faculty self-registration attempt | blocked by policy |
