# Traceability Matrix (MOD-01)

## Backend Endpoints

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-01-01 | POST /auth/verify-student-id | university validation source | SCR-007 | T01-I1, T01-I2 | backend auth router/service |
| FUN-01-02 | POST /auth/register | users + validation source + Supabase Auth | SCR-008, SCR-010, EmailVerificationPendingScreen | T01-I3, T01-I4, T01-E1 | backend auth router/service + Supabase Admin API |
| FUN-01-05 | GET /auth/me | users | app startup, SCR-004, SCR-005 | T01-U1..T01-U4, T01-I8, T01-I9, T01-E2 | backend protected route + Supabase JWT verification middleware |

## Supabase Client Operations (Mobile)

| Function ID | Operation | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-01-03 | Supabase `signInWithPassword` | Supabase Auth session | SCR-004, SCR-005 | T01-S1..T01-S3, T01-I5, T01-I6, T01-E3, T01-E4 | mobile Supabase client + auth store |
| FUN-01-04 | Supabase `refreshSession` (automatic) | Supabase Auth session | session layer | T01-S4..T01-S6, T01-I7 | mobile Supabase client + session persistence |
| FUN-01-06 | Supabase `resetPasswordForEmail` | Supabase Auth | SCR-006 | T01-S7..T01-S9, T01-E5 | mobile Supabase client + password reset screen |
| FUN-01-07 | Supabase `updateUser` (new password) | Supabase Auth | SetNewPasswordScreen | T01-S7..T01-S9, T01-E6 | mobile Supabase client + deep link handler |

## Supabase Automatic

| Function | Trigger | Data | Screens | Notes |
|---|---|---|---|---|
| Email Verification | Registration (FUN-01-02) | Supabase Auth `email_confirmed_at` | EmailVerificationPendingScreen | Supabase sends confirmation email automatically; backend syncs `email_confirmed_at` to local DB |

## Traceability Rule
Every commit touching MOD-01 should map to at least one matrix row.
