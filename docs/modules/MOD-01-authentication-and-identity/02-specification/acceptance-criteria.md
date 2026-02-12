# Acceptance Criteria

## Function-Level Acceptance

### FUN-01-01
- Given a valid student ID in dataset, endpoint returns `valid: true` and profile preview.
- Given unknown student ID, endpoint returns `valid: false`.
- Given empty or malformed student ID, endpoint returns `400`.

### FUN-01-02
- Given verified identity and valid payload, Supabase Auth user is created, local DB record is inserted, and `201` returned.
- Given duplicate email/student_id, endpoint returns validation error.
- Given unverified identity, account creation is blocked.
- Given role other than `student`, endpoint returns `403`.
- Supabase sends email verification after successful registration.
- Phone field is accepted but optional; missing phone does not block registration.

### FUN-01-03
- Given valid credentials via Supabase client `signInWithPassword`, Supabase returns session with access and refresh tokens.
- Given invalid credentials, Supabase returns authentication error.
- After login, mobile calls `GET /auth/me` and receives user profile.
- If user is inactive or email not confirmed, `GET /auth/me` returns `403`.

### FUN-01-04
- Supabase client automatically refreshes access token when expired.
- Given invalid/expired refresh token, user is redirected to login.

### FUN-01-05
- Given valid Supabase JWT, endpoint returns current user data including email_confirmed status.
- Given missing/invalid access token, returns `401`.
- Given inactive user, returns `403`.
- Given unverified email, returns `403`.
- Response never includes `password_hash`.

### FUN-01-06
- Given email on ForgotPasswordScreen, Supabase sends password reset email.
- System does not reveal whether email exists (no error on non-existent email).

### FUN-01-07
- After clicking reset link, user can set new password via Supabase client.
- New password must meet minimum requirements (min 8 characters).
- After reset, user can login with new password.

## Module-Level Acceptance
- Faculty self-registration remains blocked in all user flows.
- Auth responses follow standard success/error envelope.
- Auth behavior is consistent with screen-level flow in module docs.
- All backend auth endpoints enforce rate limiting (10 req/min).
- Email verification is enforced on all protected backend routes.
- Backend verifies Supabase JWT signature on every protected request.
