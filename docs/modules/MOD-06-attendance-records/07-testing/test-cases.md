# Test Cases (MOD-06)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T06-U1 | FUN-06-01 | first recognition event | row created |
| T06-U2 | FUN-06-01 | repeated recognition same date | row updated, no duplicate |
| T06-U3 | FUN-06-02 | summary computation | counts match records |
| T06-U4 | FUN-06-05 | invalid status in manual entry | validation error |
| T06-U5 | FUN-06-06 | inactive session | non-active response |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T06-I1 | GET /attendance/today | valid schedule | `200`, records + summary |
| T06-I2 | GET /attendance/me | student token | `200`, own records |
| T06-I3 | GET /attendance/me | faculty token | `403` |
| T06-I4 | GET /attendance | valid filters | `200`, filtered data |
| T06-I5 | POST /attendance/manual | faculty token | `201`, created/updated |
| T06-I6 | POST /attendance/manual | student token | `403` |
| T06-I7 | GET /attendance/live/{schedule_id} | active class | `200`, live roster payload |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T06-E1 | student home attendance status load | today's status visible |
| T06-E2 | student history filter flow | filtered records correct |
| T06-E3 | faculty live attendance monitoring | live roster updates visible |
| T06-E4 | faculty manual entry correction | record updated with remarks |
