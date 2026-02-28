# Function Specifications

## FUN-01-01 Verify Student Identity
Goal:
- Validate submitted `student_id` against university dataset.

Implementation:
- **Backend endpoint:** `POST /auth/verify-student-id`

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

Implementation:
- **Backend endpoint:** `POST /auth/register`
- Backend creates user in **Supabase Auth** (via Admin API) and inserts profile into local `users` table.
- Supabase sends email verification automatically on user creation.

Inputs:
- Email, password, first_name, last_name, role, student_id, phone (optional).

Process:
1. Validate request payload.
2. Confirm student identity was previously verified (or re-check source).
3. Ensure email/student_id uniqueness.
4. Create user in Supabase Auth via Admin API (`supabase.auth.admin.createUser()`).
5. Insert user profile into local `users` table with `email_confirmed_at = null`.
6. Supabase sends confirmation email to the user's email address.

Outputs:
- `201` with created user metadata and message to check email.

Validation Rules:
- Reject duplicates (email or student_id).
- Reject unverified student ID.
- Role must be `student` for self-registration flow in MVP.
- Password must meet minimum strength requirements (min 8 characters).
- Phone is optional; no verification required.

## FUN-01-03 Login
Goal:
- Authenticate user credentials and obtain session tokens.

Implementation:
- **Supabase client SDK on mobile:** `supabase.auth.signInWithPassword({ email, password })`
- No backend endpoint for login. Mobile calls Supabase directly.
- Backend enforces `is_active` and `email_confirmed` checks via JWT middleware on protected routes.

Inputs:
- Email and password (entered on mobile login screen).

Process:
1. Mobile calls `supabase.auth.signInWithPassword({ email, password })`.
2. Supabase validates credentials and returns session (access_token + refresh_token).
3. Mobile stores tokens via Supabase client (automatic).
4. Mobile calls `GET /auth/me` on backend to load user profile and confirm access.
5. Backend middleware checks `is_active` and `email_confirmed_at` before responding.

Outputs:
- Supabase session with access_token (JWT), refresh_token, expires_in.

Validation Rules:
- Supabase returns error on invalid credentials.
- Backend returns `403` on `GET /auth/me` if user is inactive or email not confirmed.
- Faculty can only login with pre-seeded accounts.

## FUN-01-04 Refresh Token
Goal:
- Renew access token without requiring re-login.

Implementation:
- **Supabase client SDK on mobile:** `supabase.auth.refreshSession()`
- Handled automatically by Supabase client when access token expires.
- No backend endpoint needed.

Inputs:
- Refresh token (managed internally by Supabase client).

Process:
1. Supabase client detects access token expiry.
2. Supabase client calls Supabase Auth to refresh session.
3. New access token is returned and stored automatically.

Outputs:
- New Supabase session with refreshed access_token and expires_in.

Validation Rules:
- If refresh token is expired or invalid, user must re-authenticate (redirect to login).
- Refresh token expiry: 7 days (Supabase default).

## FUN-01-05 Get Current User
Goal:
- Return current authenticated user profile from local database.

Implementation:
- **Backend endpoint:** `GET /auth/me`
- Requires Supabase JWT in `Authorization: Bearer <token>` header.

Inputs:
- Bearer access token (Supabase JWT).

Process:
1. Backend middleware validates Supabase JWT (verifies signature using JWT secret).
2. Extract `sub` (user ID) from JWT claims.
3. Load user profile from local `users` table.
4. Check `is_active = true` and `email_confirmed_at IS NOT NULL`.
5. Return profile payload.

Outputs:
- `200` with user profile (id, email, first_name, last_name, role, student_id, phone, email_confirmed).

Validation Rules:
- Return `401` when token missing/invalid/expired.
- Return `403` when user is inactive or email not confirmed.
- Do not expose sensitive fields (`password_hash`).

## FUN-01-06 Request Password Reset
Goal:
- Send password reset email to user.

Implementation:
- **Supabase client SDK on mobile:** `supabase.auth.resetPasswordForEmail(email, { redirectTo })`
- No backend endpoint needed.

Inputs:
- Email address (entered on ForgotPasswordScreen).

Process:
1. Mobile calls `supabase.auth.resetPasswordForEmail(email, { redirectTo: appDeepLink })`.
2. Supabase sends password reset email with a magic link.
3. Mobile shows confirmation message: "Check your email for a password reset link."

Outputs:
- Supabase sends email. No direct response data needed.

Validation Rules:
- Supabase handles email validation.
- Do not reveal whether the email exists in the system (security best practice).

## FUN-01-07 Complete Password Reset
Goal:
- Set new password after clicking reset link.

Implementation:
- **Supabase client SDK on mobile:** `supabase.auth.updateUser({ password: newPassword })`
- Called after user clicks reset link in email and is redirected back to the app.

Inputs:
- New password.

Process:
1. User clicks password reset link in email.
2. App opens via deep link with Supabase session restored.
3. Mobile calls `supabase.auth.updateUser({ password: newPassword })`.
4. Supabase updates the user's password.

Outputs:
- Success confirmation; user can now login with new password.

Validation Rules:
- New password must meet minimum strength requirements (min 8 characters).
- Reset link expires after Supabase-configured timeout.
