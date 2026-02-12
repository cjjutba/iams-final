# Screen Inventory (MOD-01)

## Included Screens
| Screen ID | Screen Name | Role | Auth Module Usage |
|---|---|---|---|
| SCR-004 | StudentLoginScreen | Student | Login via Supabase client + `GET /auth/me` |
| SCR-005 | FacultyLoginScreen | Faculty | Login via Supabase client (pre-seeded only) + `GET /auth/me` |
| SCR-006 | ForgotPasswordScreen | Student/Faculty | Password reset via Supabase client (`resetPasswordForEmail`) |
| SCR-007 | StudentRegisterStep1Screen | Student | Identity verification (`FUN-01-01`) via `POST /auth/verify-student-id` |
| SCR-008 | StudentRegisterStep2Screen | Student | Account setup payload preparation (email, phone, password) |
| SCR-010 | StudentRegisterReviewScreen | Student | Registration submit (`FUN-01-02`) via `POST /auth/register` |
| SCR-NEW | EmailVerificationPendingScreen | Student | Post-registration; instructs user to check email for verification link |
| SCR-NEW | SetNewPasswordScreen | Student/Faculty | Password reset completion via Supabase client (`updateUser`) |

## Cross-Screen Dependencies
- Registration Step 3 (`SCR-009`) is part of face module (`MOD-03`) but depends on successful auth registration sequencing.
- Session restore after login routes to role-specific home screens.
- EmailVerificationPendingScreen is shown after successful registration; user must verify email before logging in.
- SetNewPasswordScreen is shown when user opens app via password reset deep link.
