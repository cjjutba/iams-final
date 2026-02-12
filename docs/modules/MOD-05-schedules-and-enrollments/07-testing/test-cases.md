# Test Cases (MOD-05)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T05-U1 | FUN-05-01 | day filter applied (day=1) | correct filtered set, sorted by start_time ASC |
| T05-U2 | FUN-05-03 | start_time >= end_time | validation error (400) |
| T05-U3 | FUN-05-04 | faculty role query | schedules by faculty_id from JWT sub |
| T05-U4 | FUN-05-04 | student role query | schedules by enrollments join |
| T05-U5 | FUN-05-05 | roster mapping | unique enrolled student rows with id, student_id, first_name, last_name |
| T05-U6 | FUN-05-03 | invalid day_of_week (e.g., 9) | validation error (400) |
| T05-U7 | FUN-05-03 | faculty_id references non-faculty user | validation error (400) |
| T05-U8 | FUN-05-03 | room_id references non-existent room | validation error (400) |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T05-I1 | GET /schedules?day=1 | valid JWT, valid request | `200`, schedule list sorted by start_time |
| T05-I2 | GET /schedules/{id} | valid JWT, existing id | `200`, full schedule data with faculty_name and room |
| T05-I3 | GET /schedules/{id} | valid JWT, unknown id | `404` |
| T05-I4 | POST /schedules | admin JWT, valid payload | `201`, created schedule with is_active=true |
| T05-I5 | POST /schedules | non-admin JWT | `403` FORBIDDEN |
| T05-I6 | GET /schedules/me | student JWT | `200`, enrolled schedules only |
| T05-I7 | GET /schedules/me | faculty JWT | `200`, teaching schedules only |
| T05-I8 | GET /schedules/{id}/students | faculty JWT (assigned) | `200`, roster list |
| T05-I9 | GET /schedules/{id}/students | faculty JWT (not assigned) | `403` FORBIDDEN |
| T05-I10 | GET /schedules/{id}/students | student JWT (enrolled) | `200`, roster list |
| T05-I11 | GET /schedules/{id}/students | student JWT (not enrolled) | `403` FORBIDDEN |
| T05-I12 | POST /schedules | missing JWT | `401` UNAUTHORIZED |
| T05-I13 | GET /schedules/me | missing JWT | `401` UNAUTHORIZED |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T05-E1 | student schedule screen load | assigned schedules displayed grouped by day |
| T05-E2 | faculty schedule screen load | teaching schedules displayed grouped by day |
| T05-E3 | schedule detail then roster load | enrolled students displayed with student_id and name |
| T05-E4 | invalid schedule creation attempt | blocked with validation error message |
| T05-E5 | expired JWT on schedule screen | redirect to login |
