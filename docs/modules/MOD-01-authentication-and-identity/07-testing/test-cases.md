# Test Cases (MOD-01)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T01-U1 | FUN-01-05 | verify valid Supabase JWT signature | user context resolved |
| T01-U2 | FUN-01-05 | verify expired Supabase JWT | 401 unauthorized |
| T01-U3 | FUN-01-05 | verify tampered Supabase JWT | 401 unauthorized |
| T01-U4 | FUN-01-02 | validate student_id against university dataset | match found |
| T01-U5 | FUN-01-02 | validate unknown student_id | no match |
| T01-U6 | FUN-01-02 | reject weak password (< 8 chars) | validation error |
| T01-U7 | FUN-01-05 | check is_active = false | 403 forbidden |
| T01-U8 | FUN-01-05 | check email_confirmed_at = null | 403 forbidden |

## Integration Tests (Backend Endpoints)
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T01-I1 | POST /auth/verify-student-id | valid student_id | `200`, `valid: true`, profile preview |
| T01-I2 | POST /auth/verify-student-id | unknown student_id | `200`, `valid: false` |
| T01-I3 | POST /auth/verify-student-id | empty student_id | `400`, VALIDATION_ERROR |
| T01-I4 | POST /auth/register | valid payload | `201`, user created in Supabase Auth + local DB |
| T01-I5 | POST /auth/register | duplicate email | `409`, CONFLICT |
| T01-I6 | POST /auth/register | duplicate student_id | `409`, CONFLICT |
| T01-I7 | POST /auth/register | unverified student_id | `403`, FORBIDDEN |
| T01-I8 | POST /auth/register | faculty self-registration | `403`, FORBIDDEN |
| T01-I9 | POST /auth/register | missing phone (optional) | `201`, user created (phone = null) |
| T01-I10 | GET /auth/me | valid Supabase JWT, active user, email confirmed | `200`, user profile with email_confirmed=true |
| T01-I11 | GET /auth/me | missing Authorization header | `401` |
| T01-I12 | GET /auth/me | expired JWT | `401` |
| T01-I13 | GET /auth/me | inactive user (is_active=false) | `403` |
| T01-I14 | GET /auth/me | email not confirmed | `403` |

## Supabase Client Tests (Mobile-Side)
| ID | Operation | Scenario | Expected |
|---|---|---|---|
| T01-S1 | signInWithPassword | valid credentials | session with access + refresh token |
| T01-S2 | signInWithPassword | invalid credentials | AuthApiError |
| T01-S3 | signInWithPassword | email not confirmed | AuthApiError or partial session |
| T01-S4 | refreshSession | valid refresh token | new access token |
| T01-S5 | refreshSession | expired refresh token | error, redirect to login |
| T01-S6 | resetPasswordForEmail | valid email | email sent (no error) |
| T01-S7 | resetPasswordForEmail | unknown email | no error (security) |
| T01-S8 | updateUser (password) | valid new password | password updated |
| T01-S9 | updateUser (password) | weak password | error |

## Rate Limiting Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T01-R1 | POST /auth/verify-student-id | 11 requests in 1 minute | 11th request returns `429` |
| T01-R2 | POST /auth/register | 11 requests in 1 minute | 11th request returns `429` |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T01-E1 | Student registration step1 → step2 → review → register | Supabase Auth user + local DB created; email verification sent |
| T01-E2 | Student verifies email → login → `GET /auth/me` | Session restored, profile loaded |
| T01-E3 | Faculty login with pre-seeded account → `GET /auth/me` | Login success, faculty profile loaded |
| T01-E4 | Faculty self-registration attempt | Blocked by policy (no register UI for faculty; `403` if API called directly) |
| T01-E5 | Unverified user attempts login → `GET /auth/me` | `403` email not verified |
| T01-E6 | Password reset: request → email → click link → set new password → login | Password updated, login succeeds |
