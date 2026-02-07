# Authentication Module Catalog

## Subdomains
1. Identity Verification
- Student identity check against university dataset before account creation.

2. Account Registration
- Creates student account only after verification step passes.

3. Session Authentication
- Login and token issuance.

4. Session Continuity
- Refresh token flow.

5. Authenticated Identity Access
- Current user profile endpoint (`/auth/me`).

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-01-01 | Verify Student Identity | Validate student ID against approved data source |
| FUN-01-02 | Register Student Account | Create account after identity verification |
| FUN-01-03 | Login | Validate credentials and return tokens |
| FUN-01-04 | Refresh Token | Re-issue access token using refresh token |
| FUN-01-05 | Get Current User | Return authenticated user profile |

## Actors
- Student
- Faculty
- Backend API
- Mobile app
- Data import/seed operations

## Interfaces
- REST auth endpoints (`/auth/*`)
- Token verification for protected routes
- Validation data lookup (CSV/JRMSU import source)
