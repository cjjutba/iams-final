# Test Cases (MOD-06)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T06-U1 | FUN-06-01 | first recognition event | row created with status=present |
| T06-U2 | FUN-06-01 | repeated recognition same date | row updated, no duplicate |
| T06-U3 | FUN-06-02 | summary computation | counts match records (present+late+absent+early_leave=total) |
| T06-U4 | FUN-06-05 | invalid status in manual entry | 422 validation error |
| T06-U5 | FUN-06-06 | inactive session | `{ "session_active": false }` response |
| T06-U6 | FUN-06-05 | missing remarks in manual entry | 422 validation error |
| T06-U7 | FUN-06-03 | invalid date range (start > end) | 422 validation error |
| T06-U8 | FUN-06-01 | unknown student_id | silently skipped, no record created |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T06-I1 | GET /attendance/today | valid schedule + faculty JWT | 200, records + summary |
| T06-I2 | GET /attendance/me | student JWT | 200, own records only |
| T06-I3 | GET /attendance/me | faculty JWT | 200, own class records |
| T06-I4 | GET /attendance | valid filters + faculty JWT | 200, filtered data |
| T06-I5 | POST /attendance/manual | faculty JWT + valid payload | 200, created/updated with audit trail |
| T06-I6 | POST /attendance/manual | student JWT | 403 forbidden |
| T06-I7 | GET /attendance/live/{schedule_id} | active class + faculty JWT | 200, live roster payload |
| T06-I8 | GET /attendance/today | missing JWT | 401 unauthorized |
| T06-I9 | GET /attendance/today | student JWT | 403 forbidden |
| T06-I10 | GET /attendance/history | faculty JWT + unassigned schedule | 403 forbidden |
| T06-I11 | POST /attendance/manual | missing JWT | 401 unauthorized |
| T06-I12 | GET /attendance/live/{id} | student JWT | 403 forbidden |
| T06-I13 | GET /attendance/me | expired JWT | 401 unauthorized |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T06-E1 | student home attendance status load | today's status visible with correct data |
| T06-E2 | student history filter flow | filtered records correct, sorted by date DESC |
| T06-E3 | faculty live attendance monitoring | live roster updates visible with presence data |
| T06-E4 | faculty manual entry correction | record updated with remarks, success message shown |
| T06-E5 | expired JWT redirect | 401 redirects to login screen |
