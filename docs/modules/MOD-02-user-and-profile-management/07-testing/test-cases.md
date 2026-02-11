# Test Cases (MOD-02)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T02-U1 | FUN-02-03 | Update first_name (allowed field) | Accepted, persisted |
| T02-U2 | FUN-02-03 | Update phone (allowed field) | Accepted, persisted |
| T02-U3 | FUN-02-03 | Update email (immutable field) | Rejected with `400` |
| T02-U4 | FUN-02-03 | Update role by non-admin | Rejected with `403` |
| T02-U5 | FUN-02-03 | Update role by admin | Accepted, persisted |
| T02-U6 | FUN-02-01 | Pagination params validation | Valid defaults applied |
| T02-U7 | FUN-02-04 | Delete strategy — calls Supabase Admin API | User removed from both stores |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T02-I1 | GET /users | Admin Supabase JWT | `200`, paginated list with phone/email_confirmed |
| T02-I2 | GET /users | Student/faculty Supabase JWT | `403` |
| T02-I3 | GET /users/{id} | Authorized request (own record) | `200`, user data with phone, student_id, email_confirmed |
| T02-I4 | GET /users/{id} | Unknown id | `404` |
| T02-I5 | GET /users/{id} | Non-admin requesting another user | `403` |
| T02-I6 | PATCH /users/{id} | Valid payload (first_name, phone) | `200`, updated data |
| T02-I7 | PATCH /users/{id} | Email change attempt | `400` (immutable) |
| T02-I8 | PATCH /users/{id} | Restricted field (role) by non-admin | `403` |
| T02-I9 | DELETE /users/{id} | Admin request | `200`, user deleted from DB and Supabase Auth |
| T02-I10 | DELETE /users/{id} | Non-admin request | `403` |
| T02-I11 | DELETE /users/{id} | Verify face_registrations cleaned up | No orphan rows |
| T02-I12 | DELETE /users/{id} | Supabase Auth deletion fails | `500`, local changes rolled back |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T02-E1 | Student profile view — shows phone, email, student_id | All fields rendered correctly |
| T02-E2 | Student profile edit — update name and phone | Updated profile persists |
| T02-E3 | Student profile edit — attempt email change | Email field is read-only / change rejected |
| T02-E4 | Faculty profile view/edit flow | Updated profile persists; email immutable |
| T02-E5 | Unauthorized user list attempt | Blocked access |
| T02-E6 | Admin deletes user — full cleanup | User gone from DB, Supabase Auth, face registrations |
