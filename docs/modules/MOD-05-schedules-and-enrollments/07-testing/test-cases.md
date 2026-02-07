# Test Cases (MOD-05)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T05-U1 | FUN-05-01 | day filter applied | correct filtered set |
| T05-U2 | FUN-05-03 | start_time >= end_time | validation error |
| T05-U3 | FUN-05-04 | faculty role query | schedules by faculty_id |
| T05-U4 | FUN-05-04 | student role query | schedules by enrollments |
| T05-U5 | FUN-05-05 | roster mapping | unique enrolled student rows |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T05-I1 | GET /schedules?day=1 | valid request | `200`, schedule list |
| T05-I2 | GET /schedules/{id} | existing id | `200`, schedule data |
| T05-I3 | GET /schedules/{id} | unknown id | `404` |
| T05-I4 | POST /schedules | admin valid payload | `201`, created |
| T05-I5 | POST /schedules | non-admin payload | `403` |
| T05-I6 | GET /schedules/me | student token | student schedules only |
| T05-I7 | GET /schedules/me | faculty token | faculty schedules only |
| T05-I8 | GET /schedules/{id}/students | valid id | `200`, roster list |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T05-E1 | student schedule screen load | assigned schedules displayed |
| T05-E2 | faculty schedule screen load | teaching schedules displayed |
| T05-E3 | schedule detail then roster load | enrolled students displayed |
| T05-E4 | invalid schedule creation attempt | blocked with validation error |
