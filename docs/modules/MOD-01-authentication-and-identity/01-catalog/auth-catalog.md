# Authentication Module Catalog

## Auth Provider
**Supabase Auth** — Mobile uses Supabase client SDK; backend verifies Supabase JWT.

## Subdomains
1. Identity Verification
- Student identity check against university dataset before account creation.

2. Account Registration
- Creates student account in Supabase Auth + local DB only after verification step passes.
- Triggers email verification via Supabase.

3. Email Verification
- Supabase sends confirmation email on registration.
- Backend enforces email_confirmed on protected routes.

4. Session Authentication
- Login via Supabase client SDK (`signInWithPassword`).
- Backend verifies Supabase JWT on protected routes.

5. Session Continuity
- Token refresh via Supabase client SDK (automatic `refreshSession`).

6. Authenticated Identity Access
- Current user profile endpoint (`GET /auth/me`).

7. Password Recovery
- Password reset request via Supabase client (`resetPasswordForEmail`).
- Password reset completion via Supabase client (`updateUser`).

## Function Catalog
| Function ID | Name | Summary | Implementation |
|---|---|---|---|
| FUN-01-01 | Verify Student Identity | Validate student ID against approved data source | Backend endpoint |
| FUN-01-02 | Register Student Account | Create Supabase Auth user + local DB record after identity verification | Backend endpoint |
| FUN-01-03 | Login | Authenticate via Supabase client and obtain JWT | Supabase client SDK |
| FUN-01-04 | Refresh Token | Renew access token automatically | Supabase client SDK |
| FUN-01-05 | Get Current User | Return authenticated user profile from local DB | Backend endpoint |
| FUN-01-06 | Request Password Reset | Send password reset email via Supabase | Supabase client SDK |
| FUN-01-07 | Complete Password Reset | Set new password after clicking reset link | Supabase client SDK |

## Actors
- Student
- Faculty
- Backend API
- Mobile app (Supabase client SDK)
- Supabase Auth service
- Data import/seed operations

## Interfaces
- REST auth endpoints (`POST /auth/verify-student-id`, `POST /auth/register`, `GET /auth/me`)
- Supabase client SDK operations (login, refresh, password reset)
- Supabase JWT verification middleware on backend
- Validation data lookup (CSV/JRMSU import source)
