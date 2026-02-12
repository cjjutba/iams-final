# Test Cases (MOD-07)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T07-U1 | FUN-07-01 | Start valid session | Initialized state map with enrolled students |
| T07-U2 | FUN-07-03 | Detected student | miss_count reset to 0, last_seen updated |
| T07-U3 | FUN-07-03 | Missed student | miss_count incremented by 1 |
| T07-U4 | FUN-07-04 | Misses reach threshold | Early-leave event created, attendance status → early_leave |
| T07-U5 | FUN-07-05 | 8/10 scans detected | score = 80.0 |
| T07-U6 | FUN-07-04 | Already flagged student | No duplicate event (dedup enforced) |
| T07-U7 | FUN-07-05 | 0 total scans | score = 0 (safe baseline) |
| T07-U8 | FUN-07-01 | Invalid/inactive schedule | Session rejected |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T07-I1 | GET /presence/{attendance_id}/logs | Valid attendance_id, faculty JWT | `200`, logs list with envelope |
| T07-I2 | GET /presence/{attendance_id}/logs | Invalid attendance_id | `400` or `404` |
| T07-I3 | GET /presence/early-leaves | Valid schedule/date, faculty JWT | `200`, event list with envelope |
| T07-I4 | GET /presence/early-leaves | Invalid filters | `400` |
| T07-I5 | GET /presence/early-leaves | Student JWT (wrong role) | `403` |
| T07-I6 | GET /presence/{attendance_id}/logs | Missing JWT | `401` |
| T07-I7 | GET /presence/early-leaves | Missing JWT | `401` |
| T07-I8 | GET /presence/{attendance_id}/logs | Student JWT (wrong role) | `403` |
| T07-I9 | GET /presence/{attendance_id}/logs | Expired JWT | `401` |
| T07-I10 | GET /presence/early-leaves | Expired JWT | `401` |

## Scenario Tests
| ID | Flow | Expected |
|---|---|---|
| T07-S1 | Continuous presence for full session | No early-leave flag, high score |
| T07-S2 | Leave after initial presence | Early-leave flag at threshold, attendance status → early_leave |
| T07-S3 | Brief absence then recovery | No flag if misses below threshold, counter resets |
| T07-S4 | Threshold changed via config | Trigger behavior follows new `EARLY_LEAVE_THRESHOLD` value |
| T07-S5 | Auth redirect on expired JWT | Mobile redirects to login screen |
