# Auth Screen Flows

## Student Registration Flow (Auth Portion)
1. `SCR-007` StudentRegisterStep1Screen
- User enters student ID
- App calls backend `POST /auth/verify-student-id`
- App shows identity preview and confirmation ("Is this you?")

2. `SCR-008` StudentRegisterStep2Screen
- User enters/updates email, phone (optional), password
- Local validation occurs (email format, password min 8 chars)

3. `SCR-010` StudentRegisterReviewScreen
- App submits registration to backend `POST /auth/register`
- Backend creates Supabase Auth user + local DB record
- Supabase sends email verification automatically
- On success, navigate to EmailVerificationPendingScreen

4. `SCR-NEW` EmailVerificationPendingScreen
- Shows message: "We've sent a verification email to your address. Please check your inbox and click the link to verify your account."
- Provides "Resend Email" button (calls Supabase `resend` or backend proxy)
- Provides "Go to Login" button

## Student Login Flow
1. `SCR-004` StudentLoginScreen
2. Mobile calls `supabase.auth.signInWithPassword({ email, password })`
3. If Supabase returns error (invalid credentials, email not confirmed), show error on screen
4. On success, store Supabase session (automatic via Supabase client)
5. Call backend `GET /auth/me` to load profile and confirm access
6. If backend returns `403` (inactive or email unverified), show appropriate message
7. On success, route to student home area

## Faculty Login Flow
1. `SCR-005` FacultyLoginScreen
2. Mobile calls `supabase.auth.signInWithPassword({ email, password })`
3. Enforce pre-seeded faculty rule (no register link on faculty login screen)
4. Message on screen: "Faculty accounts are created by the administrator. Contact your department if you need access."
5. On success, call backend `GET /auth/me` to load profile
6. Backend checks role = faculty, is_active, email_confirmed
7. Route to faculty home area

## Password Recovery Flow
1. `SCR-006` ForgotPasswordScreen
2. User enters email address
3. Mobile calls `supabase.auth.resetPasswordForEmail(email, { redirectTo: appDeepLink })`
4. Show confirmation: "If an account exists with this email, you will receive a password reset link."
5. User clicks link in email, app opens via deep link
6. App shows "Set New Password" screen
7. Mobile calls `supabase.auth.updateUser({ password: newPassword })`
8. On success, show confirmation and navigate to login
