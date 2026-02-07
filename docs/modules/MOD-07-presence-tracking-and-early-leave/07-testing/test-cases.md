# Test Cases (MOD-07)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T07-U1 | FUN-07-01 | start valid session | initialized state map |
| T07-U2 | FUN-07-03 | detected student | miss_count reset to 0 |
| T07-U3 | FUN-07-03 | missed student | miss_count increment |
| T07-U4 | FUN-07-04 | misses reach threshold | early-leave event created |
| T07-U5 | FUN-07-05 | 8/10 scans detected | score = 80 |
| T07-U6 | FUN-07-04 | already flagged student | no duplicate event |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T07-I1 | GET /presence/{attendance_id}/logs | valid attendance_id | `200`, logs list |
| T07-I2 | GET /presence/{attendance_id}/logs | invalid attendance_id | `400` or `404` |
| T07-I3 | GET /presence/early-leaves | valid schedule/date | `200`, event list |
| T07-I4 | GET /presence/early-leaves | invalid filters | `400` |
| T07-I5 | GET /presence/early-leaves | unauthorized role | `403` |

## Scenario Tests
| ID | Flow | Expected |
|---|---|---|
| T07-S1 | continuous presence for full session | no early-leave flag, high score |
| T07-S2 | leave after initial presence | early-leave flag at threshold |
| T07-S3 | brief absence then recovery | no flag if misses below threshold |
| T07-S4 | threshold changed via config | trigger behavior follows new value |
