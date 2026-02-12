# Demo Checklist (MOD-01)

- [ ] Student ID verification returns expected valid/invalid responses.
- [ ] Student registration creates Supabase Auth user + local DB record.
- [ ] Email verification email is sent after registration.
- [ ] Duplicate registration (email or student_id) is rejected with `409`.
- [ ] Faculty self-registration path is not available (no register UI; API returns `403`).
- [ ] Student login via Supabase client works with valid credentials.
- [ ] Login with unverified email is blocked (`403` on `GET /auth/me`).
- [ ] Login with inactive account is blocked (`403` on `GET /auth/me`).
- [ ] Faculty login works with pre-seeded account.
- [ ] Token refresh works automatically via Supabase client.
- [ ] `GET /auth/me` returns correct authenticated user payload (including phone, email_confirmed).
- [ ] Invalid/expired token requests return `401`.
- [ ] Password reset email is sent via Supabase.
- [ ] Password reset completion updates password; user can login with new password.
- [ ] Phone field is optional during registration (registration succeeds without phone).
