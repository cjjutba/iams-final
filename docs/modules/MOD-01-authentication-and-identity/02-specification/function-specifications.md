# Function Specifications

## FUN-01-01 Verify Student Identity
Goal:
- Validate submitted `student_id` against university dataset.

Inputs:
- `student_id` (string)

Process:
1. Normalize and validate `student_id` format.
2. Query imported university identity source.
3. Return profile preview if valid.

Outputs:
- `200` with `valid: true` and identity fields, or `valid: false`.

Validation Rules:
- Reject empty/invalid format with `400`.
- Do not create user in this function.

## FUN-01-02 Register Student Account
Goal:
- Create student account only after identity verification success.

Inputs:
- Email, password, first_name, last_name, role, student_id.

Process:
1. Validate request payload.
2. Confirm student identity was previously verified (or re-check source).
3. Ensure email/student_id uniqueness.
4. Hash password and create account.

Outputs:
- `201` with created user metadata.

Validation Rules:
- Reject duplicates.
- Reject unverified student ID.
- Role must be `student` for self-registration flow in MVP.

## FUN-01-03 Login
Goal:
- Authenticate user credentials and issue session tokens.

Inputs:
- Email and password.

Process:
1. Fetch user by email.
2. Verify password hash.
3. Enforce active account status.
4. Issue access token (+ refresh token depending on auth mode).

Outputs:
- `200` with access/refresh tokens and expiry metadata.

Validation Rules:
- Return `401` on invalid credentials.
- Return `403` for blocked/inactive users.

## FUN-01-04 Refresh Token
Goal:
- Exchange valid refresh token for a new access token.

Inputs:
- Refresh token.

Process:
1. Validate refresh token integrity and expiry.
2. Resolve user context.
3. Issue new access token.

Outputs:
- `200` with renewed access token.

Validation Rules:
- Return `401` if refresh token is invalid/expired.

## FUN-01-05 Get Current User
Goal:
- Return current authenticated user profile.

Inputs:
- Bearer access token.

Process:
1. Validate bearer token.
2. Resolve user identity and role.
3. Return profile payload.

Outputs:
- `200` with user profile.

Validation Rules:
- Return `401` when token missing/invalid.
- Do not expose sensitive fields (`password_hash`).
