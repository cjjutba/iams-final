# Business Rules

## Auth Provider
Supabase Auth is the authentication provider for IAMS. All rules below apply within the Supabase Auth context.

## Registration Rules
1. Student registration requires successful identity verification first (`FUN-01-01`).
2. Student ID must match university-provided dataset.
3. Email and student_id must be unique in both Supabase Auth and local user store.
4. Faculty cannot self-register in MVP.
5. Phone number is collected during registration but is optional and does not require verification.
6. Backend creates user in Supabase Auth (via Admin API) and inserts profile into local `users` table.

## Email Verification Rules
1. Supabase sends a confirmation email automatically when a user is created via registration.
2. Users must verify their email before they can access protected resources.
3. Backend enforces `email_confirmed_at IS NOT NULL` on protected route access.
4. Unverified users who attempt to access protected endpoints receive `403 FORBIDDEN` with message "Email not verified."

## Login Rules
1. Login is performed via Supabase client SDK on mobile (`signInWithPassword`).
2. Faculty uses pre-seeded account credentials.
3. Inactive users (`is_active = false`) are blocked on protected route access (backend returns `403`).
4. Users with unverified email are blocked on protected route access (backend returns `403`).

## Session Rules
1. Supabase-issued JWT (access token) is required for all protected backend endpoints.
2. Access token expiry: 30 minutes (configurable in Supabase project settings).
3. Refresh token expiry: 7 days (Supabase default).
4. Supabase client handles token refresh automatically.
5. Invalid/expired tokens must return `401` from backend.
6. If refresh fails, mobile redirects user to login screen.

## Password Reset Rules
1. Password reset is initiated via Supabase client SDK (`resetPasswordForEmail`).
2. Supabase sends reset email with a magic link.
3. User clicks link, app opens via deep link, and user sets new password via `updateUser`.
4. The system must not reveal whether an email exists in the system when requesting a reset.

## Security Rules
1. Passwords are hashed by Supabase Auth (bcrypt, cost factor 12).
2. JWT secret and Supabase keys come from environment variables only.
3. API responses must not return password hashes or sensitive internals.
4. All auth-related traffic must use HTTPS in production.
5. Tokens must not be logged or exposed in error messages.
6. Backend must validate Supabase JWT signature on every protected request.
