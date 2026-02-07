# Test Cases (MOD-02)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T02-U1 | FUN-02-03 | allowed profile field update | accepted |
| T02-U2 | FUN-02-03 | restricted field update by non-admin | rejected |
| T02-U3 | FUN-02-01 | pagination params validation | valid defaults applied |
| T02-U4 | FUN-02-04 | deactivate strategy application | user marked inactive |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T02-I1 | GET /users | admin token | `200`, paginated list |
| T02-I2 | GET /users | student/faculty token | `403` |
| T02-I3 | GET /users/{id} | authorized request | `200`, user data |
| T02-I4 | GET /users/{id} | unknown id | `404` |
| T02-I5 | PATCH /users/{id} | valid payload | `200`, updated data |
| T02-I6 | PATCH /users/{id} | restricted payload | `400` or `403` |
| T02-I7 | DELETE /users/{id} | admin request | `200`, operation success |
| T02-I8 | DELETE /users/{id} | non-admin request | `403` |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T02-E1 | student profile view/edit flow | updated profile persists |
| T02-E2 | faculty profile view/edit flow | updated profile persists |
| T02-E3 | unauthorized user list attempt | blocked access |
| T02-E4 | deactivate user then auth check | inactive user cannot log in |
